foreach required_env {RUN_ROOT INPUT_CHECKPOINT CTS_TAG} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set run_root [file normalize $::env(RUN_ROOT)]
set tag $::env(CTS_TAG)
set profile core
if {[info exists ::env(ASIC_PROFILE)]} {
    set profile [string tolower [string trim $::env(ASIC_PROFILE)]]
}
switch -- $profile {
    core { set top snn_ecg_asic_core_top }
    axi { set top snn_ecg_axi_asic_top }
    default { error "ASIC_PROFILE must be core or axi, got: $profile" }
}

set report_dir [file join $run_root reports cts_rerun $tag]
set output_dir [file join $run_root outputs cts_rerun $tag]
file mkdir $report_dir
file mkdir $output_dir

setMultiCpuUsage -localCpu 8
restoreDesign [file normalize $::env(INPUT_CHECKPOINT)] $top
setAnalysisMode -analysisType onChipVariation -cppr both
setDelayCalMode -SIAware true

set_ccopt_property buffer_cells {CLKBUFX2 CLKBUFX3 CLKBUFX4 CLKBUFX6 CLKBUFX8 CLKBUFX12 CLKBUFX16 CLKBUFX20}
set_ccopt_property inverter_cells {CLKINVX1 CLKINVX2 CLKINVX3 CLKINVX4 CLKINVX6 CLKINVX8 CLKINVX12 CLKINVX16 CLKINVX20}
set_ccopt_property use_inverters true
set_ccopt_property -net_type top target_max_trans 55ps
set_ccopt_property -net_type trunk target_max_trans 55ps
set_ccopt_property -net_type leaf target_max_trans 50ps
set spec_file [file join $output_dir ccopt_50ps.spec]
create_ccopt_clock_tree_spec -file $spec_file
source $spec_file
clock_opt_design
optDesign -postCTS
optDesign -postCTS -hold
report_ccopt_clock_trees -file [file join $report_dir ccopt_clock_trees_50ps.rpt]
report_ccopt_skew_groups -file [file join $report_dir ccopt_skew_groups_50ps.rpt]

setNanoRouteMode -routeWithTimingDriven true
setNanoRouteMode -routeWithSiDriven true
routeDesign -globalDetail -viaOpt -wireOpt
setExtractRCMode -engine postRoute -effortLevel high -coupled true
extractRC
optDesign -postRoute
optDesign -postRoute -hold
routeDesign -wireOpt
extractRC

timeDesign -postRoute -outDir [file join $report_dir time_design_setup]
timeDesign -postRoute -hold -outDir [file join $report_dir time_design_hold]
report_timing -view setup_slow -late -max_paths 50 > [file join $report_dir timing_setup.rpt]
report_timing -view hold_fast -early -max_paths 50 > [file join $report_dir timing_hold.rpt]
report_area > [file join $report_dir area.rpt]

set_ccopt_property -net_type top target_max_trans 60ps
set_ccopt_property -net_type trunk target_max_trans 60ps
set_ccopt_property -net_type leaf target_max_trans 60ps
report_ccopt_clock_trees -file [file join $report_dir ccopt_clock_trees_60ps_final.rpt]
verify_drc -report [file join $report_dir internal_route_drc.rpt]
verifyConnectivity -type regular -report [file join $report_dir connectivity_signal.rpt]
checkPlace > [file join $report_dir check_place.rpt]

set_default_switching_activity -input_activity 0.10 -seq_activity 0.10
report_power -view setup_slow -format detailed > [file join $report_dir power_vectorless.rpt]

saveDesign [file join $output_dir ${top}_${tag}.enc]
defOut -netlist -floorplan -routing [file join $output_dir ${top}_${tag}.def]
saveNetlist [file join $output_dir ${top}_${tag}.v]
write_sdf -max_view setup_slow -min_view hold_fast -recompute_delay_calc \
    -version 3.0 [file join $output_dir ${top}_${tag}.sdf]
rcOut -rc_corner max_rc -spef [file join $output_dir ${top}_${tag}_max_rc.spef]
rcOut -rc_corner min_rc -spef [file join $output_dir ${top}_${tag}_min_rc.spef]
exit
