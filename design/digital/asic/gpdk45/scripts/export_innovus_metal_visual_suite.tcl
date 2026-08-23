foreach required_env {LAYOUT_CHECKPOINT VISUAL_OUTPUT_DIR} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set checkpoint [file normalize $::env(LAYOUT_CHECKPOINT)]
set output_dir [file normalize $::env(VISUAL_OUTPUT_DIR)]
set top snn_ecg_axi_asic_top
file mkdir $output_dir
set status [open [file join $output_dir metal_visual_export_status.txt] w]

proc set_visible {status_handle object value} {
    set result [catch {setLayerPreference $object -isVisible $value} message]
    puts $status_handle "$object|visible=$value|status=$result|$message"
    flush $status_handle
}

proc dump_group {status_handle output_dir name visible_metals} {
    for {set layer 1} {$layer <= 11} {incr layer} {
        set_visible $status_handle Metal${layer} 0
    }
    for {set via 1} {$via <= 10} {incr via} {
        set_visible $status_handle Via${via} 0
    }
    foreach metal $visible_metals {
        set_visible $status_handle $metal 1
    }
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
set_visible $status pinObj 0
set_visible $status inst 0
set_visible $status net 1
deselectAll

dump_group $status $output_dir 07_metal1_only {Metal1}
dump_group $status $output_dir 08_metal2_3 {Metal2 Metal3}
dump_group $status $output_dir 09_metal4_6 {Metal4 Metal5 Metal6}
dump_group $status $output_dir 10_metal7_11 {Metal7 Metal8 Metal9 Metal10 Metal11}

close $status
exit
