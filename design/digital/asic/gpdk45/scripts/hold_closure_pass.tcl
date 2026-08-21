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

set target_slack 0.000
if {[info exists ::env(HOLD_TARGET_SLACK)]} {
    set target_slack $::env(HOLD_TARGET_SLACK)
}

set hold_slack_threshold -0.200
if {[info exists ::env(HOLD_SLACK_THRESHOLD)]} {
    set hold_slack_threshold $::env(HOLD_SLACK_THRESHOLD)
}

set hold_cells {DLY1X1 DLY2X1 DLY3X1 DLY4X1}
if {[info exists ::env(HOLD_CELL_SET)]} {
    set hold_cells [split [string trim $::env(HOLD_CELL_SET)]]
}
if {[llength $hold_cells] == 0} {
    error "HOLD_CELL_SET must name at least one delay cell"
}

set eco_passes 1
if {[info exists ::env(HOLD_ECO_PASSES)]} {
    set eco_passes $::env(HOLD_ECO_PASSES)
}
if {![string is integer -strict $eco_passes] || $eco_passes < 1 || $eco_passes > 3} {
    error "HOLD_ECO_PASSES must be an integer from 1 to 3"
}

set route_mode wireOpt
if {[info exists ::env(HOLD_ROUTE_MODE)]} {
    set route_mode [string trim $::env(HOLD_ROUTE_MODE)]
}
if {$route_mode ni {wireOpt none}} {
    error "HOLD_ROUTE_MODE must be wireOpt or none"
}

set report_dir [file join $run_root reports hold_closure $profile $tag]
set output_dir [file join $run_root outputs hold_closure $profile $tag]
file mkdir $report_dir
file mkdir $output_dir

setMultiCpuUsage -localCpu 8
# The portable checkpoint archive intentionally excludes the generated
# NanoRoute rc_model.bin cache.  LEF, Liberty and QRC links are revalidated by
# the launcher, and this script performs a fresh high-effort extraction before
# any optimization or report.  Permit restore of that one missing cache.
set restore_db_file_check 0
restoreDesign $checkpoint $top
setAnalysisMode -analysisType onChipVariation -cppr both
setDelayCalMode -SIAware true
setExtractRCMode -engine postRoute -effortLevel high -coupled true
extractRC

timeDesign -postRoute -outDir [file join $report_dir baseline_setup]
timeDesign -postRoute -hold -outDir [file join $report_dir baseline_hold]
report_timing -view setup_slow -late -max_paths 100 \
    > [file join $report_dir baseline_timing_setup.rpt]
report_timing -view hold_fast -early -max_paths 500 \
    > [file join $report_dir baseline_timing_hold.rpt]

# Preserve the existing 100 ps hold uncertainty and OCV assumptions.  The
# previous automatic flow protected setup TNS so aggressively that short hold
# paths remained even with a positive target.  Run-3 has more than 2 ns of
# setup margin, so permit a small setup-TNS trade.  GSCLIB045 provides dedicated
# DLY cells; restricting this pass to those cells avoids another broad buffer
# insertion sweep and directly targets the residual minimum-delay paths.
setOptMode -opt_add_insts true
setOptMode -opt_move_insts true
setOptMode -opt_fix_fanout_load true
setOptMode -opt_hold_allow_overlap true
setOptMode -opt_hold_allow_resize true
setOptMode -opt_hold_allow_setup_tns_degradation true
setOptMode -opt_add_repeater_report_failure_reason true
setOptMode -opt_hold_cells $hold_cells
# Lower fixing bound: paths worse than this threshold are excluded.  A zero
# value would exclude every negative-slack path instead of selecting it.
setOptMode -opt_hold_slack_threshold $hold_slack_threshold
setOptMode -opt_hold_target_slack $target_slack
setOptMode -opt_max_density 0.90
setOptMode -opt_verbose true

setNanoRouteMode -routeWithTimingDriven true
setNanoRouteMode -routeWithSiDriven true

for {set pass 1} {$pass <= $eco_passes} {incr pass} {
    optDesign -postRoute -hold
    # optDesign performs its own incremental EcoRoute.  A subsequent global
    # wire-opt pass can be enabled for a broad closure run, but it is optional
    # because it may perturb thousands of already-routed nets for a small ECO.
    if {$route_mode eq "wireOpt"} {
        routeDesign -wireOpt
    }
    extractRC

    set pass_dir [file join $report_dir pass_$pass]
    file mkdir $pass_dir
    timeDesign -postRoute -outDir [file join $pass_dir time_design_setup]
    timeDesign -postRoute -hold -outDir [file join $pass_dir time_design_hold]
    report_timing -view setup_slow -late -max_paths 100 \
        > [file join $pass_dir timing_setup.rpt]
    report_timing -view hold_fast -early -max_paths 500 \
        > [file join $pass_dir timing_hold.rpt]
}

set final_dir [file join $report_dir final]
file mkdir $final_dir
report_area > [file join $final_dir area.rpt]
verify_drc -report [file join $final_dir internal_route_drc.rpt]
verifyConnectivity -type regular -report [file join $final_dir connectivity_signal.rpt]
checkPlace > [file join $final_dir check_place.rpt]

set_ccopt_property -net_type top target_max_trans 60ps
set_ccopt_property -net_type trunk target_max_trans 60ps
set_ccopt_property -net_type leaf target_max_trans 60ps
report_ccopt_clock_trees -file [file join $final_dir ccopt_clock_trees_60ps.rpt]
report_ccopt_skew_groups -file [file join $final_dir ccopt_skew_groups.rpt]

set output_base [file join $output_dir ${top}_${tag}]
saveDesign -rc ${output_base}.enc
saveNetlist ${output_base}.v
defOut -netlist -floorplan -routing ${output_base}.def

set config [open [file join $report_dir run_config.txt] w]
puts $config "profile=$profile"
puts $config "top=$top"
puts $config "input_checkpoint=$checkpoint"
puts $config "hold_target_slack_ns=$target_slack"
puts $config "hold_slack_threshold_ns=$hold_slack_threshold"
puts $config "hold_eco_passes=$eco_passes"
puts $config "hold_route_mode=$route_mode"
puts $config "hold_cells=[join $hold_cells { }]"
puts $config "hold_allow_setup_tns_degradation=true"
puts $config "generated_rc_model_cache=excluded_then_high_effort_reextracted"
puts $config "ocv_and_hold_uncertainty=preserved_from_checkpoint"
close $config

exit
