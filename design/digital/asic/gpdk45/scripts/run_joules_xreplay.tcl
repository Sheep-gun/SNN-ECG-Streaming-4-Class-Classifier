foreach required_env {
    RUN_ROOT PDK_ROOT RTL_STIM MAPPED_NETLIST MAPPED_SDC MAP_FILE
    ACTIVITY_TAG DUT_INSTANCE
} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set run_root [file normalize $::env(RUN_ROOT)]
set pdk_root [file normalize $::env(PDK_ROOT)]
set profile core
if {[info exists ::env(ASIC_PROFILE)]} {
    set profile [string tolower [string trim $::env(ASIC_PROFILE)]]
}
switch -- $profile {
    core {
        set top snn_ecg_asic_core_top
        set clock clk
    }
    axi {
        set top snn_ecg_axi_asic_top
        set clock s_axi_aclk
    }
    default { error "ASIC_PROFILE must be core or axi, got: $profile" }
}

set activity_dir [file join $run_root activity_gate]
set report_dir [file join $run_root reports joules]
file mkdir $activity_dir
file mkdir $report_dir

set tag $::env(ACTIVITY_TAG)
set output_activity [file join $activity_dir ${top}_${tag}.saif]
set missing_report [file join $report_dir ${top}_${tag}_missing_signals.rpt]
set annotation_report [file join $report_dir ${top}_${tag}_annotation.rpt]
set xrun_path [string trim [exec which xrun]]
set cell_model [file join $pdk_root verilog slow_vdd1v2_basicCells.v]
read_libs [file join $pdk_root timing slow_vdd1v2_basicCells.lib]
set post_cts_arg {}
if {[info exists ::env(POST_CTS_NETLIST)] && $::env(POST_CTS_NETLIST)} {
    set post_cts_arg -post_cts_netlist
}

set replay_status [catch {
    xreplay \
        -xrun_path $xrun_path \
        -netlist [list [file normalize $::env(MAPPED_NETLIST)]] \
        $post_cts_arg \
        -sdc [file normalize $::env(MAPPED_SDC)] \
        -top $top \
        -map_file [file normalize $::env(MAP_FILE)] genus \
        -rtl_stim [file normalize $::env(RTL_STIM)] \
        -stim_format shm \
        -dut_instance $::env(DUT_INSTANCE) \
        -clocks $clock \
        -delay_mode zero \
        -verilog_model_files [list $cell_model] \
        -xreplay_output_stim_format saif \
        -out $output_activity \
        -report_missing_signals all \
        -out_report_file $missing_report \
        -stim_annotation {state port:in seq:both bbox:both macro:both mem:both} \
        -stim_annotation_report_file $annotation_report \
        -trace_arcs all
} replay_message]

if {($replay_status == 0) && (![file exists $output_activity] || [file size $output_activity] == 0)} {
    set replay_status 1
    set replay_message "xreplay returned without producing a non-empty SAIF"
}

set status_file [open [file join $report_dir ${top}_${tag}_xreplay_status.txt] w]
puts $status_file "status=$replay_status"
puts $status_file "profile=$profile"
puts $status_file "rtl_stim=$::env(RTL_STIM)"
puts $status_file "output_activity=$output_activity"
puts $status_file "output_format=SAIF"
puts $status_file $replay_message
close $status_file

if {$replay_status != 0} {
    error "Joules xreplay failed: $replay_message"
}
exit
