foreach required_env {RUN_ROOT INPUT_CHECKPOINT ASIC_PROFILE CTS_TAG HOLD_ENDPOINTS_FILE} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set run_root [file normalize $::env(RUN_ROOT)]
set checkpoint [file normalize $::env(INPUT_CHECKPOINT)]
set profile [string tolower [string trim $::env(ASIC_PROFILE)]]
set tag [string trim $::env(CTS_TAG)]
switch -- $profile {
    core { set top snn_ecg_asic_core_top }
    axi { set top snn_ecg_axi_asic_top }
    default { error "ASIC_PROFILE must be core or axi" }
}

set endpoint_handle [open [file normalize $::env(HOLD_ENDPOINTS_FILE)] r]
set endpoint_payload [read $endpoint_handle]
close $endpoint_handle
set endpoints {}
set seen [dict create]
foreach raw [split $endpoint_payload "\n"] {
    set pin [string trim $raw]
    if {$pin eq ""} { continue }
    if {![string match */D $pin] || [regexp {\s} $pin]} {
        error "Invalid hold endpoint: $pin"
    }
    if {[dict exists $seen $pin]} { error "Duplicate hold endpoint: $pin" }
    dict set seen $pin 1
    lappend endpoints $pin
}
if {[llength $endpoints] == 0} { error "No hold endpoints supplied" }

set report_dir [file join $run_root reports prects_hold_rerun $profile $tag]
set output_dir [file join $run_root outputs prects_hold_rerun $profile $tag]
file mkdir $report_dir
file mkdir $output_dir

setMultiCpuUsage -localCpu 8
set restore_db_file_check 0
restoreDesign $checkpoint $top
setAnalysisMode -analysisType onChipVariation -cppr both
setDelayCalMode -SIAware true

# Insert the known run-2 violated endpoints before CTS so clock and signal
# routing can be rebuilt around the minimum-delay cells instead of patched
# after routing.
set applied [open [file join $report_dir prects_endpoint_ecos.csv] w]
puts $applied "index,endpoint,cell"
set index 0
foreach pin $endpoints {
    incr index
    set inst_name [format "PRECTS_HOLD_ECO_%04d" $index]
    set net_name [format "PRECTS_HOLD_NET_%04d" $index]
    ecoAddRepeater -term $pin -cell DLY4X1 -relativeDistToSink 0.05 \
        -name $inst_name -newNetName $net_name
    puts $applied "$index,$pin,DLY4X1"
}
close $applied
refinePlace
checkPlace > [file join $report_dir check_place_prects.rpt]

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

setOptMode -opt_hold_allow_overlap true
setOptMode -opt_hold_allow_resize true
setOptMode -opt_hold_allow_setup_tns_degradation true
setOptMode -opt_hold_cells {DLY1X1 DLY2X1 DLY3X1 DLY4X1}
# Cadence defines this as a lower fixing bound: paths worse than the threshold
# are excluded.  Use -200 ps so the observed -75 ps post-CTS paths are included;
# zero would incorrectly exclude every negative-slack path.
setOptMode -opt_hold_slack_threshold -0.200
setOptMode -opt_hold_target_slack 0.000
setOptMode -opt_add_repeater_report_failure_reason true
optDesign -postCTS
optDesign -postCTS -hold
report_ccopt_clock_trees -file [file join $report_dir ccopt_clock_trees_postcts.rpt]

setNanoRouteMode -routeWithTimingDriven true
setNanoRouteMode -routeWithSiDriven true
routeDesign -globalDetail -viaOpt -wireOpt
setExtractRCMode -engine postRoute -effortLevel high -coupled true
extractRC

setOptMode -opt_fix_fanout_load true
setOptMode -opt_drv true
optDesign -postRoute -drv
optDesign -postRoute -hold
routeDesign -wireOpt
extractRC

timeDesign -postRoute -outDir [file join $report_dir time_design_setup]
timeDesign -postRoute -hold -outDir [file join $report_dir time_design_hold]
report_timing -view setup_slow -late -max_paths 200 \
    > [file join $report_dir timing_setup.rpt]
report_timing -view hold_fast -early -max_paths 1000 \
    > [file join $report_dir timing_hold.rpt]
report_area > [file join $report_dir area.rpt]
verify_drc -report [file join $report_dir internal_route_drc.rpt]
verifyConnectivity -type regular -report [file join $report_dir connectivity_signal.rpt]
checkPlace > [file join $report_dir check_place_final.rpt]
set_ccopt_property -net_type top target_max_trans 60ps
set_ccopt_property -net_type trunk target_max_trans 60ps
set_ccopt_property -net_type leaf target_max_trans 60ps
report_ccopt_clock_trees -file [file join $report_dir ccopt_clock_trees_60ps.rpt]

set_default_switching_activity -input_activity 0.10 -seq_activity 0.10
report_power -view setup_slow -format detailed \
    > [file join $report_dir power_vectorless.rpt]

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
puts $config "prects_hold_endpoints=[llength $endpoints]"
puts $config "prects_hold_cell=DLY4X1"
puts $config "clock_targets_ps=top55_trunk55_leaf50_final_report60"
puts $config "ocv_and_hold_uncertainty=preserved_from_checkpoint"
close $config
exit
