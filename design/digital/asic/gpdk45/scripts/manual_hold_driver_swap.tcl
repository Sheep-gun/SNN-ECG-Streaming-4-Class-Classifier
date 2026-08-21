foreach required_env {RUN_ROOT INPUT_CHECKPOINT ASIC_PROFILE HOLD_TAG HOLD_SWAP_PLAN} {
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
    default { error "ASIC_PROFILE must be core or axi" }
}

set plan_handle [open [file normalize $::env(HOLD_SWAP_PLAN)] r]
set plan_lines [split [read $plan_handle] "\n"]
close $plan_handle
if {[lindex $plan_lines 0] ne "endpoint,instance,old_cell,new_cell"} {
    error "Unexpected hold-swap plan header"
}

set report_dir [file join $run_root reports hold_driver_swap $profile $tag]
set output_dir [file join $run_root outputs hold_driver_swap $profile $tag]
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

set applied [open [file join $report_dir applied_swaps.csv] w]
puts $applied "endpoint,instance,old_cell,new_cell"
set swap_count 0
foreach line [lrange $plan_lines 1 end] {
    set line [string trim $line]
    if {$line eq ""} { continue }
    set fields [split $line ","]
    if {[llength $fields] != 4} {
        error "Malformed hold-swap row: $line"
    }
    lassign $fields endpoint instance old_cell new_cell
    set inst_ptr [dbGet -e -p top.insts.name $instance]
    if {$inst_ptr eq "" || $inst_ptr eq "0x0"} {
        error "Swap instance not found: $instance"
    }
    set actual_cell [dbGet $inst_ptr.cell.name]
    if {$actual_cell ne $old_cell} {
        error "Swap precondition failed for $instance: expected $old_cell got $actual_cell"
    }
    ecoChangeCell -inst $instance -cell $new_cell
    puts $applied "$endpoint,$instance,$old_cell,$new_cell"
    incr swap_count
}
close $applied
if {$swap_count == 0} { error "No hold-driver swaps were applied" }

# Equivalent drive variants retain the same logical pins and nets.  Do not run
# global or ECO rerouting; preserve the run-2 route and re-extract parasitics.
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
puts $config "swap_plan=[file normalize $::env(HOLD_SWAP_PLAN)]"
puts $config "swap_count=$swap_count"
puts $config "routing_preserved=true"
puts $config "ocv_and_hold_uncertainty=preserved_from_checkpoint"
close $config
exit
