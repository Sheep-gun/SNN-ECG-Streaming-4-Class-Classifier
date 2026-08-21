foreach required_env {RUN_ROOT FINAL_CHECKPOINT ASIC_PROFILE FINAL_TAG} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set run_root [file normalize $::env(RUN_ROOT)]
set checkpoint [file normalize $::env(FINAL_CHECKPOINT)]
set profile [string tolower [string trim $::env(ASIC_PROFILE)]]
set tag [string trim $::env(FINAL_TAG)]
switch -- $profile {
    core { set top snn_ecg_asic_core_top }
    axi { set top snn_ecg_axi_asic_top }
    default { error "ASIC_PROFILE must be core or axi, got: $profile" }
}

set report_dir [file join $run_root reports hold_closed_final $profile $tag]
set output_dir [file join $run_root outputs hold_closed_final $profile $tag]
file mkdir $report_dir
file mkdir $output_dir

setMultiCpuUsage -localCpu 8
set restore_db_file_check 0
restoreDesign $checkpoint $top
setAnalysisMode -analysisType onChipVariation -cppr both
setDelayCalMode -SIAware true
setExtractRCMode -engine postRoute -effortLevel high -coupled true
extractRC

timeDesign -postRoute -outDir [file join $report_dir time_design_setup]
timeDesign -postRoute -hold -outDir [file join $report_dir time_design_hold]
report_timing -view setup_slow -late -max_paths 200 \
    > [file join $report_dir timing_setup.rpt]
report_timing -view hold_fast -early -max_paths 1000 \
    > [file join $report_dir timing_hold.rpt]
report_area > [file join $report_dir area.rpt]

set_default_switching_activity -input_activity 0.10 -seq_activity 0.10
report_power -view setup_slow -format detailed \
    > [file join $report_dir power_vectorless.rpt]

verify_drc -report [file join $report_dir internal_route_drc.rpt]
verifyConnectivity -type regular -report [file join $report_dir connectivity_signal.rpt]
checkPlace > [file join $report_dir check_place.rpt]
set_ccopt_property -net_type top target_max_trans 60ps
set_ccopt_property -net_type trunk target_max_trans 60ps
set_ccopt_property -net_type leaf target_max_trans 60ps
report_ccopt_clock_trees -file [file join $report_dir ccopt_clock_trees_60ps.rpt]
report_ccopt_skew_groups -file [file join $report_dir ccopt_skew_groups.rpt]

set output_base [file join $output_dir ${top}_${tag}]
saveDesign -rc ${output_base}.enc
saveNetlist ${output_base}.v
defOut -netlist -floorplan -routing ${output_base}.def
write_sdf -max_view setup_slow -min_view hold_fast -recompute_delay_calc \
    -version 3.0 ${output_base}.sdf
rcOut -rc_corner max_rc -spef ${output_base}_max_rc.spef
rcOut -rc_corner min_rc -spef ${output_base}_min_rc.spef

set config [open [file join $report_dir run_config.txt] w]
puts $config "profile=$profile"
puts $config "top=$top"
puts $config "input_checkpoint=$checkpoint"
puts $config "extraction=IQuantus_postRoute_high_coupled"
puts $config "analysis=MMMC_OCV_CPPR_both_SI_on"
puts $config "vectorless_activity=input_0.10_seq_0.10"
puts $config "ocv_and_hold_uncertainty=preserved_from_checkpoint"
close $config
exit
