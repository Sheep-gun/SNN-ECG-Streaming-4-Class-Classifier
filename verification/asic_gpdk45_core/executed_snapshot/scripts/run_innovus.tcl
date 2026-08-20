foreach required_env {RUN_ROOT PDK_ROOT} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set script_dir [file dirname [file normalize [info script]]]
set run_root [file normalize $::env(RUN_ROOT)]
set pdk_root [file normalize $::env(PDK_ROOT)]
set top snn_ecg_asic_core_top
set report_dir [file join $run_root reports innovus]
set output_dir [file join $run_root outputs innovus]
set tech_lef [file join $pdk_root lef gsclib045_tech.lef]
set macro_lef [file join $pdk_root lef gsclib045_macro.lef]
set mapped_netlist [file join $run_root outputs genus ${top}_mapped.v]

file mkdir $report_dir
file mkdir $output_dir

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

floorPlan -site CoreSite -su 1.0 0.65 20 20 20 20 -coreMarginsBy die
createRow -site CoreSiteDouble
assignIoPins -pin *
setPlaceMode -place_global_ignore_scan true
checkDesign -all > [file join $report_dir check_design_init.rpt]

placeDesign
optDesign -preCTS
report_timing -max_paths 20 > [file join $report_dir timing_postplace.rpt]
report_area > [file join $report_dir area_postplace.rpt]
saveDesign [file join $output_dir ${top}_postplace.enc]

set_ccopt_property buffer_cells {CLKBUFX2 CLKBUFX3 CLKBUFX4 CLKBUFX6 CLKBUFX8 CLKBUFX12}
set_ccopt_property inverter_cells {CLKINVX1 CLKINVX2 CLKINVX3 CLKINVX4 CLKINVX6 CLKINVX8}
set ccopt_spec [file join $output_dir ccopt.spec]
create_ccopt_clock_tree_spec -file $ccopt_spec
source $ccopt_spec
clock_opt_design
optDesign -postCTS
report_timing -max_paths 20 > [file join $report_dir timing_postcts.rpt]
report_ccopt_clock_trees -file [file join $report_dir ccopt_clock_trees.rpt]
report_ccopt_skew_groups -file [file join $report_dir ccopt_skew_groups.rpt]

setNanoRouteMode -routeWithTimingDriven true
setNanoRouteMode -routeWithSiDriven true
routeDesign
saveDesign [file join $output_dir ${top}_routed_preextract.enc]
defOut -netlist -floorplan -routing [file join $output_dir ${top}_routed_preextract.def]
set extraction_engine "IQuantus high effort"
set extraction_status [catch {
    setExtractRCMode -engine postRoute -effortLevel high -coupled true
    extractRC
} extraction_message]
if {$extraction_status != 0} {
    set extraction_engine "TQuantus medium effort fallback"
    setExtractRCMode -engine postRoute -effortLevel medium -coupled true
    extractRC
}
set extraction_log [open [file join $report_dir extraction_engine.txt] w]
puts $extraction_log "engine=$extraction_engine"
puts $extraction_log "initial_high_effort_status=$extraction_status"
puts $extraction_log $extraction_message
close $extraction_log

optDesign -postRoute
optDesign -postRoute -hold
extractRC

# Preserve the routed database before optional reporting/export commands.
# This core-only study does not build a VDD/VSS ring or stripe network.
saveDesign [file join $output_dir ${top}_routed_postextract.enc]
defOut -netlist -floorplan -routing [file join $output_dir ${top}_routed_checkpoint.def]
saveNetlist [file join $output_dir ${top}_postroute_checkpoint.v]

timeDesign -postRoute -outDir [file join $report_dir time_design_setup]
timeDesign -postRoute -hold -outDir [file join $report_dir time_design_hold]
report_timing -view setup_slow -late -max_paths 50 > [file join $report_dir timing_postroute_setup.rpt]
report_timing -view hold_fast -early -max_paths 50 > [file join $report_dir timing_postroute_hold.rpt]
report_area > [file join $report_dir area_postroute.rpt]
verifyConnectivity -type regular -report [file join $report_dir connectivity_signal_postroute.rpt]

set power_status [catch {
    set_default_switching_activity -input_activity 0.10 -seq_activity 0.10
    report_power > [file join $report_dir power_postroute_vectorless.rpt]
} power_message]
set power_log [open [file join $report_dir power_command_status.txt] w]
puts $power_log "status=$power_status"
puts $power_log $power_message
close $power_log

defOut -netlist -floorplan -routing [file join $output_dir ${top}_routed.def]
saveNetlist [file join $output_dir ${top}_postroute.v]
write_sdf \
    -max_view setup_slow \
    -min_view hold_fast \
    -version 3.0 \
    [file join $output_dir ${top}_postroute.sdf]
rcOut -rc_corner max_rc -spef [file join $output_dir ${top}_postroute_max_rc.spef]
rcOut -rc_corner min_rc -spef [file join $output_dir ${top}_postroute_min_rc.spef]
saveDesign [file join $output_dir ${top}_routed.enc]

exit
