foreach required_env {LAYOUT_CHECKPOINT VISUAL_OUTPUT_DIR} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set checkpoint [file normalize $::env(LAYOUT_CHECKPOINT)]
set output_dir [file normalize $::env(VISUAL_OUTPUT_DIR)]
set top snn_ecg_axi_asic_top
file mkdir $output_dir

set status [open [file join $output_dir native_visual_export_status.txt] w]

proc try_command {status_handle label command} {
    set result [catch {uplevel #0 $command} message]
    puts $status_handle "$label|status=$result|$message"
    flush $status_handle
    return $result
}

proc dump_native {status_handle output_dir name} {
    fit
    set output [file join $output_dir ${name}.gif]
    set result [catch {dumpToGIF $output} message]
    puts $status_handle "dump_${name}|status=$result|$message"
    flush $status_handle
    if {$result != 0} {
        error "dumpToGIF failed for $name: $message"
    }
}

set restore_db_file_check 0
restoreDesign $checkpoint $top

try_command $status pin_hidden {setLayerPreference pinObj -isVisible 0}
try_command $status instances_visible {setLayerPreference inst -isVisible 1}
try_command $status nets_visible {setLayerPreference net -isVisible 1}
try_command $status deselect_full {deselectAll}
dump_native $status $output_dir 01_full_placement_routing

try_command $status placement_nets_hidden {setLayerPreference net -isVisible 0}
try_command $status placement_instances_visible {setLayerPreference inst -isVisible 1}
try_command $status deselect_placement {deselectAll}
dump_native $status $output_dir 02_placement_only

try_command $status routing_instances_hidden {setLayerPreference inst -isVisible 0}
try_command $status routing_nets_visible {setLayerPreference net -isVisible 1}
try_command $status deselect_routing {deselectAll}
dump_native $status $output_dir 03_routing_only

try_command $status pins_instances_visible {setLayerPreference inst -isVisible 1}
try_command $status pins_nets_visible {setLayerPreference net -isVisible 1}
try_command $status pins_visible {setLayerPreference pinObj -isVisible 1}
try_command $status deselect_pins {deselectAll}
dump_native $status $output_dir 04_full_with_pins

try_command $status clock_pin_hidden {setLayerPreference pinObj -isVisible 0}
try_command $status clock_instances_visible {setLayerPreference inst -isVisible 1}
try_command $status clock_nets_visible {setLayerPreference net -isVisible 1}
try_command $status deselect_clock {deselectAll}
set clock_net_ptrs [dbGet -p top.nets.isClock 1]
set clock_net_names [dbGet $clock_net_ptrs.name]
puts $status "clock_net_count=[llength $clock_net_names]"
if {[llength $clock_net_names] > 0} {
    try_command $status select_clock_nets [list selectNet $clock_net_names]
}
dump_native $status $output_dir 05_clock_nets_selected

try_command $status qrs_nets_hidden {setLayerPreference net -isVisible 0}
try_command $status qrs_instances_visible {setLayerPreference inst -isVisible 1}
try_command $status deselect_qrs {deselectAll}
set qrs_names [dbGet top.insts.name *u_qrs_maf*]
puts $status "qrs_maf_leaf_instance_count=[llength $qrs_names]"
if {[llength $qrs_names] > 0} {
    try_command $status select_qrs_maf [list selectInst $qrs_names]
    if {[try_command $status fit_qrs_selected {fit -selected}] != 0} {
        fit
    }
}
set qrs_output [file join $output_dir 06_qrs_maf_placement_selected.gif]
if {[catch {dumpToGIF $qrs_output} qrs_message] != 0} {
    error "dumpToGIF failed for qrs_maf selection: $qrs_message"
}
puts $status "dump_06_qrs_maf_placement_selected|status=0|$qrs_message"

close $status
exit
