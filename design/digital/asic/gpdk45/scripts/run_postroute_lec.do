tclmode
set_screen_display -noprogress
set_dofile_abort exit

foreach required_env {TOP SLOW_LIB MAPPED_NETLIST POSTROUTE_NETLIST LEC_REPORT_DIR} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

file mkdir $::env(LEC_REPORT_DIR)
set_log_file [file join $::env(LEC_REPORT_DIR) postroute_lec.log] -replace
set_parallel_option -threads 1,4 -norelease_license
set_compare_options -threads 1,4
set_mapping_method -sensitive
set_undefined_cell black_box -noascend -both
set_undriven_signal 0 -both
read_library -liberty -both $::env(SLOW_LIB)

read_design -verilog95 -golden -lastmod -noelab $::env(MAPPED_NETLIST)
elaborate_design -golden -root $::env(TOP)
read_design -verilog95 -revised -lastmod -noelab $::env(POSTROUTE_NETLIST)
elaborate_design -revised -root $::env(TOP)

report_black_box > [file join $::env(LEC_REPORT_DIR) black_boxes.rpt]
set_flatten_model -seq_constant
set_flatten_model -seq_constant_x_to 0
set_flatten_model -hier_seq_merge
set_flatten_model -balanced_modeling

set_system_mode lec
add_compared_points -all
compare
report_verification -verbose > [file join $::env(LEC_REPORT_DIR) verification.rpt]
report_unmapped_points -summary > [file join $::env(LEC_REPORT_DIR) unmapped_final.rpt]

set total_count [get_compare_points -count]
set diff_count [get_compare_points -NONequivalent -count]
set abort_count [get_compare_points -abort -count]
set unknown_count [get_compare_points -unknown -count]
set summary_file [open [file join $::env(LEC_REPORT_DIR) result_summary.txt] w]
puts $summary_file "total=$total_count"
puts $summary_file "non_equivalent=$diff_count"
puts $summary_file "abort=$abort_count"
puts $summary_file "unknown=$unknown_count"
close $summary_file

if {($total_count == 0) || ($diff_count != 0) || ($abort_count != 0) || ($unknown_count != 0)} {
    error "Post-route LEC failed: total=$total_count diff=$diff_count abort=$abort_count unknown=$unknown_count"
}
exit 0
