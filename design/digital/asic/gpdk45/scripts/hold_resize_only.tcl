foreach required_env {RUN_ROOT INPUT_CHECKPOINT ASIC_PROFILE HOLD_TAG} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set run_root [file normalize $::env(RUN_ROOT)]
set checkpoint [file normalize $::env(INPUT_CHECKPOINT)]
set profile [string tolower [string trim $::env(ASIC_PROFILE)]]
set tag [string trim $::env(HOLD_TAG)]
switch -- $profile {
    core { set top snn_ecg_asic_core_top }
    axi { set top snn_ecg_axi_asic_top }
    default { error "ASIC_PROFILE must be core or axi, got: $profile" }
}

set target_slack 0.010
if {[info exists ::env(HOLD_TARGET_SLACK)]} {
    set target_slack $::env(HOLD_TARGET_SLACK)
}

set report_dir [file join $run_root reports hold_resize_only $profile $tag]
set output_dir [file join $run_root outputs hold_resize_only $profile $tag]
file mkdir $report_dir
file mkdir $output_dir

setMultiCpuUsage -localCpu 8
set restore_db_file_check 0
restoreDesign $checkpoint $top
setAnalysisMode -analysisType onChipVariation -cppr both
setDelayCalMode -SIAware true
setExtractRCMode -engine postRoute -effortLevel high -coupled true
extractRC

timeDesign -postRoute -outDir [file join $report_dir baseline_setup]
timeDesign -postRoute -hold -outDir [file join $report_dir baseline_hold]

# Preserve the routed topology: forbid new instances and placement movement,
# permit only function-equivalent library-cell resizing on violated hold paths.
setOptMode -opt_add_insts false
setOptMode -opt_move_insts false
setOptMode -opt_hold_allow_resize true
setOptMode -opt_hold_allow_setup_tns_degradation true
setOptMode -opt_hold_slack_threshold 0.000
setOptMode -opt_hold_target_slack $target_slack
setOptMode -opt_verbose true
optDesign -postRoute -hold
ecoRoute -target
extractRC

timeDesign -postRoute -outDir [file join $report_dir final_setup]
timeDesign -postRoute -hold -outDir [file join $report_dir final_hold]
report_timing -view setup_slow -late -max_paths 200 \
    > [file join $report_dir timing_setup.rpt]
report_timing -view hold_fast -early -max_paths 1000 \
    > [file join $report_dir timing_hold.rpt]
report_area > [file join $report_dir area.rpt]
verify_drc -report [file join $report_dir internal_route_drc.rpt]
verifyConnectivity -type regular -report [file join $report_dir connectivity_signal.rpt]
checkPlace > [file join $report_dir check_place.rpt]

set_ccopt_property -net_type top target_max_trans 60ps
set_ccopt_property -net_type trunk target_max_trans 60ps
set_ccopt_property -net_type leaf target_max_trans 60ps
report_ccopt_clock_trees -file [file join $report_dir ccopt_clock_trees_60ps.rpt]

set output_base [file join $output_dir ${top}_${tag}]
saveDesign -rc ${output_base}.enc
saveNetlist ${output_base}.v
defOut -netlist -floorplan -routing ${output_base}.def

set config [open [file join $report_dir run_config.txt] w]
puts $config "profile=$profile"
puts $config "top=$top"
puts $config "input_checkpoint=$checkpoint"
puts $config "hold_target_slack_ns=$target_slack"
puts $config "new_instances=false"
puts $config "move_instances=false"
puts $config "hold_resize=true"
puts $config "route_mode=eco_target"
puts $config "ocv_and_hold_uncertainty=preserved_from_checkpoint"
close $config
exit
