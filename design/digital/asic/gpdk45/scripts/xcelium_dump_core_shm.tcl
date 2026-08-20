if {![info exists dump_path]} {
    error "Set dump_path before sourcing xcelium_dump_core_shm.tcl"
}

database -open core_activity -shm -into $dump_path
probe -create -database core_activity tb_snn_ecg_asic_core_manifest.dut -all -depth all
run
database -close core_activity
exit
