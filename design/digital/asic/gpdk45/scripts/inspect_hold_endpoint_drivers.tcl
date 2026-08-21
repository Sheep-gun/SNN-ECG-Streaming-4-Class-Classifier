foreach required_env {INPUT_CHECKPOINT ASIC_PROFILE HOLD_ENDPOINTS_FILE DRIVER_REPORT} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set checkpoint [file normalize $::env(INPUT_CHECKPOINT)]
set profile [string tolower [string trim $::env(ASIC_PROFILE)]]
switch -- $profile {
    core { set top snn_ecg_asic_core_top }
    axi { set top snn_ecg_axi_asic_top }
    default { error "ASIC_PROFILE must be core or axi" }
}

set restore_db_file_check 0
restoreDesign $checkpoint $top

set handle [open [file normalize $::env(HOLD_ENDPOINTS_FILE)] r]
set payload [read $handle]
close $handle
set report [open [file normalize $::env(DRIVER_REPORT)] w]
puts $report "endpoint|term_ptr|net_name|connected_terms|connected_cells"

foreach raw [split $payload "\n"] {
    set pin [string trim $raw]
    if {$pin eq ""} { continue }
    set term_ptr [dbGet -e -p top.insts.instTerms.name $pin]
    if {$term_ptr eq "" || $term_ptr eq "0x0"} {
        error "Endpoint pin not found: $pin"
    }
    set net_name [dbGet $term_ptr.net.name]
    set term_names [dbGet $term_ptr.net.allTerms.name]
    set term_cells [dbGet $term_ptr.net.allTerms.inst.cell.name]
    puts $report "$pin|$term_ptr|$net_name|$term_names|$term_cells"
}
close $report
exit
