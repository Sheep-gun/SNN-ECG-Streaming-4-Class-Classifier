foreach required_env {RUN_ROOT PDK_ROOT MAPPED_NETLIST CLOSURE_TAG FLOORPLAN_UTILIZATION} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set run_root [file normalize $::env(RUN_ROOT)]
set pdk_root [file normalize $::env(PDK_ROOT)]
set mapped_netlist [file normalize $::env(MAPPED_NETLIST)]
set tag [string trim $::env(CLOSURE_TAG)]
set utilization $::env(FLOORPLAN_UTILIZATION)
if {![string is double -strict $utilization] || $utilization < 0.35 || $utilization > 0.65} {
    error "FLOORPLAN_UTILIZATION must be from 0.35 through 0.65"
}

set drv_passes 3
if {[info exists ::env(DRV_PASSES)]} {
    set drv_passes $::env(DRV_PASSES)
}
if {![string is integer -strict $drv_passes] || $drv_passes < 1 || $drv_passes > 5} {
    error "DRV_PASSES must be an integer from 1 through 5"
}

set top snn_ecg_axi_asic_top
set script_dir [file dirname [file normalize [info script]]]
set report_dir [file join $run_root reports low_density_closure $tag]
set output_dir [file join $run_root outputs low_density_closure $tag]
file mkdir $report_dir
file mkdir $output_dir

set tech_lef [file join $pdk_root lef gsclib045_tech.lef]
set macro_lef [file join $pdk_root lef gsclib045_macro.lef]

proc report_stage {stage report_root output_root top} {
    set stage_dir [file join $report_root $stage]
    file mkdir $stage_dir
    timeDesign -postRoute -outDir [file join $stage_dir time_design_setup]
    timeDesign -postRoute -hold -outDir [file join $stage_dir time_design_hold]
    report_timing -view setup_slow -late -max_paths 200 \
        > [file join $stage_dir timing_setup.rpt]
    report_timing -view hold_fast -early -max_paths 1000 \
        > [file join $stage_dir timing_hold.rpt]
    report_area > [file join $stage_dir area.rpt]
    saveDesign -rc [file join $output_root ${top}_${stage}.enc]
}

setMultiCpuUsage -localCpu 8
set init_top_cell $top
set init_design_uniquify 1
set init_mmmc_file [file join $script_dir mmmc.tcl]
set init_lef_file [list $tech_lef $macro_lef]
set init_verilog $mapped_netlist
set init_pwr_net VDD
set init_gnd_net VSS
init_design

globalNetConnect VDD -type pgpin -pin VDD -all
globalNetConnect VSS -type pgpin -pin VSS -all
setDesignMode -process 45
setAnalysisMode -analysisType onChipVariation -cppr both
set_timing_derate -early 0.95 -late 1.00 -delay_corner slow_delay
set_timing_derate -early 1.00 -late 1.05 -delay_corner fast_delay
setDelayCalMode -SIAware true

floorPlan -site CoreSite -su 1.0 $utilization 20 20 20 20 -coreMarginsBy die
createRow -site CoreSiteDouble
assignIoPins -pin *
checkDesign -all > [file join $report_dir check_design_init.rpt]

setOptMode -opt_max_density 0.80
setOptMode -opt_add_insts true
setOptMode -opt_move_insts true
setOptMode -opt_fix_fanout_load true
setOptMode -opt_add_repeater_report_failure_reason true
setOptMode -opt_verbose true

placeDesign
optDesign -preCTS
report_area > [file join $report_dir area_postplace.rpt]
report_timing -view setup_slow -late -max_paths 100 \
    > [file join $report_dir timing_postplace_setup.rpt]
saveDesign [file join $output_dir ${top}_postplace.enc]

set_ccopt_property buffer_cells {CLKBUFX2 CLKBUFX3 CLKBUFX4 CLKBUFX6 CLKBUFX8 CLKBUFX12 CLKBUFX16 CLKBUFX20}
set_ccopt_property inverter_cells {CLKINVX1 CLKINVX2 CLKINVX3 CLKINVX4 CLKINVX6 CLKINVX8 CLKINVX12 CLKINVX16 CLKINVX20}
set_ccopt_property use_inverters true
set_ccopt_property -net_type top target_max_trans 55ps
set_ccopt_property -net_type trunk target_max_trans 55ps
set_ccopt_property -net_type leaf target_max_trans 50ps
set ccopt_spec [file join $output_dir ccopt_50ps.spec]
create_ccopt_clock_tree_spec -file $ccopt_spec
source $ccopt_spec
clock_opt_design

setOptMode -opt_hold_allow_overlap true
setOptMode -opt_hold_allow_resize true
setOptMode -opt_hold_allow_setup_tns_degradation true
setOptMode -opt_hold_cells {DLY1X1 DLY2X1 DLY3X1 DLY4X1}
setOptMode -opt_hold_slack_threshold -0.200
setOptMode -opt_hold_target_slack 0.000
optDesign -postCTS
optDesign -postCTS -hold
report_ccopt_clock_trees -file [file join $report_dir ccopt_clock_trees_postcts.rpt]
saveDesign [file join $output_dir ${top}_postcts.enc]

setNanoRouteMode -routeWithTimingDriven true
setNanoRouteMode -routeWithSiDriven true
routeDesign -globalDetail -viaOpt -wireOpt
setExtractRCMode -engine postRoute -effortLevel high -coupled true
extractRC
report_stage routed_baseline $report_dir $output_dir $top

setOptMode -fixCap true -fixTran true -fixFanoutLoad true
setOptMode -detailDrvFailureReason true
setOptMode -detailDrvFailureReasonMaxNumNets 300

for {set pass 1} {$pass <= $drv_passes} {incr pass} {
    optDesign -postRoute -drv
    extractRC
    optDesign -postRoute -hold
    extractRC
    report_stage [format "closure_pass_%d" $pass] $report_dir $output_dir $top
}

set final_stage [format "closure_pass_%d" $drv_passes]
set final_dir [file join $report_dir final]
file mkdir $final_dir
set_ccopt_property -net_type top target_max_trans 60ps
set_ccopt_property -net_type trunk target_max_trans 60ps
set_ccopt_property -net_type leaf target_max_trans 60ps
report_ccopt_clock_trees -file [file join $final_dir ccopt_clock_trees_60ps.rpt]
report_ccopt_skew_groups -file [file join $final_dir ccopt_skew_groups.rpt]
verify_drc -report [file join $final_dir internal_route_drc.rpt]
verifyConnectivity -type regular -report [file join $final_dir connectivity_signal.rpt]
checkPlace > [file join $final_dir check_place.rpt]

set_default_switching_activity -input_activity 0.10 -seq_activity 0.10
report_power -view setup_slow -format detailed \
    > [file join $final_dir power_vectorless.rpt]

set final_base [file join $output_dir ${top}_${tag}_final]
saveDesign -rc ${final_base}.enc
saveNetlist ${final_base}.v
defOut -netlist -floorplan -routing ${final_base}.def

set config [open [file join $report_dir run_config.txt] w]
puts $config "top=$top"
puts $config "mapped_netlist=$mapped_netlist"
puts $config "floorplan_utilization=$utilization"
puts $config "drv_passes=$drv_passes"
puts $config "hold_slack_threshold_ns=-0.200"
puts $config "hold_target_slack_ns=0.000"
puts $config "engineering_derates=slow_early_0.95_fast_late_1.05"
puts $config "analysis=MMMC_OCV_CPPR_SI_IQuantus_high"
puts $config "final_stage=$final_stage"
close $config
exit
