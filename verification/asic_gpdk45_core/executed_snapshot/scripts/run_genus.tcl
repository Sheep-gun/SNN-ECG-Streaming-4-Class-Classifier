foreach required_env {RUN_ROOT PDK_ROOT} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set script_dir [file dirname [file normalize [info script]]]
set repo_root [file normalize [file join $script_dir .. .. .. .. ..]]
set run_root [file normalize $::env(RUN_ROOT)]
set pdk_root [file normalize $::env(PDK_ROOT)]
set top snn_ecg_asic_core_top
set slow_lib [file join $pdk_root timing slow_vdd1v2_basicCells.lib]
set sdc_file [file join $repo_root design digital asic gpdk45 constraints core_100mhz.sdc]
set report_dir [file join $run_root reports genus]
set output_dir [file join $run_root outputs genus]
set mapped_v [file join $output_dir ${top}_mapped.v]
set mapped_sdc [file join $output_dir ${top}_mapped.sdc]

file mkdir $report_dir
file mkdir $output_dir
file mkdir [file join $run_root logs]

source [file join $script_dir rtl_files.tcl]
set_db init_hdl_search_path $rtl_include_dirs
set_db information_level 2

read_libs $slow_lib
read_hdl -v2001 $rtl_files
elaborate $top
check_design -unresolved > [file join $report_dir check_design_unresolved.rpt]
read_sdc $sdc_file

set effort medium
if {[info exists ::env(GENUS_EFFORT)]} {
    set effort $::env(GENUS_EFFORT)
}
set_db syn_generic_effort $effort
set_db syn_map_effort $effort
set_db syn_opt_effort $effort

syn_generic
report_area > [file join $report_dir area_generic.rpt]
report_timing -max_paths 20 > [file join $report_dir timing_generic.rpt]

syn_map
syn_opt -logical

report_qor > [file join $report_dir qor_mapped.rpt]
report_area > [file join $report_dir area_mapped.rpt]
report_gates > [file join $report_dir gates_mapped.rpt]
report_timing -max_paths 50 > [file join $report_dir timing_mapped.rpt]
report_power > [file join $report_dir power_mapped_vectorless.rpt]
report_messages > [file join $report_dir messages.rpt]

write_hdl > $mapped_v
write_sdc > $mapped_sdc
write_do_lec \
    -golden_design fv_map \
    -revised_design $mapped_v \
    -no_exit \
    -logfile [file join $run_root logs genus_final_netlist_lec.log] \
    > [file join $output_dir fv_map_to_final_netlist.do]

exit
