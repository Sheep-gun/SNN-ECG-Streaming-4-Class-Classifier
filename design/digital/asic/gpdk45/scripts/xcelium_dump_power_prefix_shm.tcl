if {![info exists dump_path] && [info exists ::env(DUMP_PATH)]} {
    set dump_path [file normalize $::env(DUMP_PATH)]
}
if {![info exists dump_path]} {
    error "Set dump_path or DUMP_PATH before sourcing xcelium_dump_power_prefix_shm.tcl"
}

set tb_scope tb_snn_ecg_asic_power_prefix.dut
if {[info exists dump_scope]} {
    set tb_scope $dump_scope
}

# First run stops at ASIC_POWER_PREFIX_WINDOW_BEGIN before the first measured
# rising edge. Open the activity database only for the matched power window.
run
database -open prefix_activity -shm -into $dump_path
probe -create -database prefix_activity $tb_scope -all -depth all

# Second run stops at ASIC_POWER_PREFIX_WINDOW_END on the matched falling edge.
run
database -close prefix_activity

# Resume once more so the testbench performs its checks and exits normally.
run
exit
