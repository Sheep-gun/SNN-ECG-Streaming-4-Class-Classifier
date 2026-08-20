foreach required_env {RUN_ROOT INPUT_CHECKPOINT CLOSURE_TAG} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set run_root [file normalize $::env(RUN_ROOT)]
set tag $::env(CLOSURE_TAG)
set profile core
if {[info exists ::env(ASIC_PROFILE)]} {
    set profile [string tolower [string trim $::env(ASIC_PROFILE)]]
}
switch -- $profile {
    core { set top snn_ecg_asic_core_top }
    axi { set top snn_ecg_axi_asic_top }
    default { error "ASIC_PROFILE must be core or axi, got: $profile" }
}

set report_dir [file join $run_root reports closure $tag]
set output_dir [file join $run_root outputs closure $tag]
file mkdir $report_dir
file mkdir $output_dir

setMultiCpuUsage -localCpu 8
restoreDesign [file normalize $::env(INPUT_CHECKPOINT)] $top
setAnalysisMode -analysisType onChipVariation -cppr both
setDelayCalMode -SIAware true
setOptMode -fixCap true -fixTran true -fixFanoutLoad true
if {[info exists ::env(HOLD_TARGET_SLACK)]} {
    setOptMode -holdTargetSlack $::env(HOLD_TARGET_SLACK)
}

optDesign -postRoute
optDesign -postRoute -hold
routeDesign -wireOpt
setExtractRCMode -engine postRoute -effortLevel high -coupled true
extractRC

timeDesign -postRoute -outDir [file join $report_dir time_design_setup]
timeDesign -postRoute -hold -outDir [file join $report_dir time_design_hold]
report_timing -view setup_slow -late -max_paths 50 \
    > [file join $report_dir timing_setup.rpt]
report_timing -view hold_fast -early -max_paths 50 \
    > [file join $report_dir timing_hold.rpt]
report_area > [file join $report_dir area.rpt]
verifyConnectivity -type regular -report [file join $report_dir connectivity_signal.rpt]
verifyGeometry > [file join $report_dir geometry_internal.rpt]

set_default_switching_activity -input_activity 0.10 -seq_activity 0.10
report_power -view setup_slow -format detailed \
    > [file join $report_dir power_vectorless.rpt]

saveDesign [file join $output_dir ${top}_${tag}.enc]
defOut -netlist -floorplan -routing [file join $output_dir ${top}_${tag}.def]
saveNetlist [file join $output_dir ${top}_${tag}.v]
write_sdf -max_view setup_slow -min_view hold_fast -recompute_delay_calc \
    -version 3.0 [file join $output_dir ${top}_${tag}.sdf]
rcOut -rc_corner max_rc -spef [file join $output_dir ${top}_${tag}_max_rc.spef]
rcOut -rc_corner min_rc -spef [file join $output_dir ${top}_${tag}_min_rc.spef]

exit
