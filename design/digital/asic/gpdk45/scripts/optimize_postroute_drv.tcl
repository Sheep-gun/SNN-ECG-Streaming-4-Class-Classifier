foreach required_env {RUN_ROOT INPUT_CHECKPOINT DRV_TAG} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set run_root [file normalize $::env(RUN_ROOT)]
set tag $::env(DRV_TAG)
set profile core
if {[info exists ::env(ASIC_PROFILE)]} {
    set profile [string tolower [string trim $::env(ASIC_PROFILE)]]
}
switch -- $profile {
    core { set top snn_ecg_asic_core_top }
    axi { set top snn_ecg_axi_asic_top }
    default { error "ASIC_PROFILE must be core or axi, got: $profile" }
}

set report_dir [file join $run_root reports drv_closure $tag]
set output_dir [file join $run_root outputs drv_closure $tag]
file mkdir $report_dir
file mkdir $output_dir

set route_mode wireOpt
if {[info exists ::env(DRV_ROUTE_MODE)]} {
    set route_mode [string trim $::env(DRV_ROUTE_MODE)]
}
if {$route_mode ni {wireOpt none}} {
    error "DRV_ROUTE_MODE must be wireOpt or none"
}

setMultiCpuUsage -localCpu 8
set restore_db_file_check 0
restoreDesign [file normalize $::env(INPUT_CHECKPOINT)] $top
setAnalysisMode -analysisType onChipVariation -cppr both
setDelayCalMode -SIAware true
setOptMode -fixCap true -fixTran true -fixFanoutLoad true
setOptMode -detailDrvFailureReason true
setOptMode -detailDrvFailureReasonMaxNumNets 100

# The restored geometry checkpoint does not persist the extracted RC database.
setExtractRCMode -engine postRoute -effortLevel high -coupled true
extractRC
optDesign -postRoute -drv
# optDesign performs incremental routing.  Keep the broader global wire-opt
# pass selectable because it can perturb already-closed short hold paths.
if {$route_mode eq "wireOpt"} {
    routeDesign -wireOpt
}
extractRC

timeDesign -postRoute -outDir [file join $report_dir time_design_setup]
timeDesign -postRoute -hold -outDir [file join $report_dir time_design_hold]
report_timing -view setup_slow -late -max_paths 50 \
    > [file join $report_dir timing_setup.rpt]
report_timing -view hold_fast -early -max_paths 50 \
    > [file join $report_dir timing_hold.rpt]
report_area > [file join $report_dir area.rpt]

set_ccopt_property -net_type top target_max_trans 60ps
set_ccopt_property -net_type trunk target_max_trans 60ps
set_ccopt_property -net_type leaf target_max_trans 60ps
report_ccopt_clock_trees -file [file join $report_dir ccopt_clock_trees_60ps.rpt]
verify_drc -report [file join $report_dir internal_route_drc.rpt]
verifyConnectivity -type regular -report [file join $report_dir connectivity_signal.rpt]
checkPlace > [file join $report_dir check_place.rpt]

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

set config [open [file join $report_dir run_config.txt] w]
puts $config "profile=$profile"
puts $config "top=$top"
puts $config "input_checkpoint=[file normalize $::env(INPUT_CHECKPOINT)]"
puts $config "drv_route_mode=$route_mode"
puts $config "analysis=MMMC_OCV_CPPR_SI_IQuantus_high"
close $config
exit
