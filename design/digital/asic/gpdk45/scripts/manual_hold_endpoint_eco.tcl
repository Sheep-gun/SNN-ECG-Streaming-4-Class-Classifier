foreach required_env {RUN_ROOT INPUT_CHECKPOINT ASIC_PROFILE HOLD_TAG HOLD_ENDPOINTS_FILE} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set run_root [file normalize $::env(RUN_ROOT)]
set checkpoint [file normalize $::env(INPUT_CHECKPOINT)]
set endpoints_file [file normalize $::env(HOLD_ENDPOINTS_FILE)]
set profile [string tolower [string trim $::env(ASIC_PROFILE)]]
set tag [string trim $::env(HOLD_TAG)]

switch -- $profile {
    core { set top snn_ecg_asic_core_top }
    axi { set top snn_ecg_axi_asic_top }
    default { error "ASIC_PROFILE must be core or axi, got: $profile" }
}

set delay_cell DLY1X1
if {[info exists ::env(HOLD_DELAY_CELL)]} {
    set delay_cell [string trim $::env(HOLD_DELAY_CELL)]
}
set relative_distance 0.05
if {[info exists ::env(HOLD_RELATIVE_DISTANCE)]} {
    set relative_distance $::env(HOLD_RELATIVE_DISTANCE)
}
set name_prefix RUN3_HOLD
if {[info exists ::env(HOLD_NAME_PREFIX)]} {
    set name_prefix [string trim $::env(HOLD_NAME_PREFIX)]
}
set route_mode global
if {[info exists ::env(HOLD_ROUTE_MODE)]} {
    set route_mode [string tolower [string trim $::env(HOLD_ROUTE_MODE)]]
}
if {$route_mode ni {global eco}} {
    error "HOLD_ROUTE_MODE must be global or eco"
}
if {![regexp {^[A-Za-z][A-Za-z0-9_]*$} $name_prefix]} {
    error "HOLD_NAME_PREFIX must be an alphanumeric Tcl/netlist identifier"
}

set endpoint_handle [open $endpoints_file r]
set endpoint_payload [read $endpoint_handle]
close $endpoint_handle
set endpoints {}
set seen [dict create]
foreach line [split $endpoint_payload "\n"] {
    set pin [string trim $line]
    if {$pin eq ""} {
        continue
    }
    if {![string match */D $pin] || [regexp {\s} $pin]} {
        error "Invalid hold endpoint pin: $pin"
    }
    if {[dict exists $seen $pin]} {
        error "Duplicate hold endpoint pin: $pin"
    }
    dict set seen $pin 1
    lappend endpoints $pin
}
if {[llength $endpoints] == 0} {
    error "No hold endpoints were provided"
}

set report_dir [file join $run_root reports manual_hold_eco $profile $tag]
set output_dir [file join $run_root outputs manual_hold_eco $profile $tag]
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
report_timing -view setup_slow -late -max_paths 100 \
    > [file join $report_dir baseline_timing_setup.rpt]
report_timing -view hold_fast -early -max_paths 500 \
    > [file join $report_dir baseline_timing_hold.rpt]

set applied [open [file join $report_dir applied_endpoint_ecos.csv] w]
puts $applied "index,endpoint,cell,relative_distance"
set index 0
foreach pin $endpoints {
    incr index
    set instance_name [format "%s_ECO_%04d" $name_prefix $index]
    set net_name [format "%s_NET_%04d" $name_prefix $index]
    ecoAddRepeater -term $pin -cell $delay_cell \
        -relativeDistToSink $relative_distance \
        -name $instance_name -newNetName $net_name
    puts $applied "$index,$pin,$delay_cell,$relative_distance"
}
close $applied

setNanoRouteMode -routeWithTimingDriven true
setNanoRouteMode -routeWithSiDriven true
# The first endpoint batch needs global/detail routing because the restored
# baseline has no ECO guides.  Follow-up batches can use targeted ecoRoute to
# preserve the already-closed routes and avoid exposing a new near-zero path on
# every full global reroute.
if {$route_mode eq "eco"} {
    ecoRoute -target
} else {
    routeDesign -globalDetail -viaOpt -wireOpt
}
extractRC

timeDesign -postRoute -outDir [file join $report_dir final_setup]
timeDesign -postRoute -hold -outDir [file join $report_dir final_hold]
report_timing -view setup_slow -late -max_paths 100 \
    > [file join $report_dir timing_setup.rpt]
report_timing -view hold_fast -early -max_paths 500 \
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
puts $config "endpoint_file=$endpoints_file"
puts $config "endpoint_count=[llength $endpoints]"
puts $config "delay_cell=$delay_cell"
puts $config "relative_distance_to_sink=$relative_distance"
puts $config "name_prefix=$name_prefix"
puts $config "route_mode=$route_mode"
puts $config "ocv_and_hold_uncertainty=preserved_from_checkpoint"
puts $config "generated_rc_model_cache=excluded_then_high_effort_reextracted"
close $config

exit
