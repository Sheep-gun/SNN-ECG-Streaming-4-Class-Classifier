if {![info exists ::env(RUN_ROOT)]} {
    error "RUN_ROOT must point to the extracted run directory"
}

set run_root $::env(RUN_ROOT)
set top snn_ecg_asic_core_top
set checkpoint [file join $run_root outputs innovus ${top}_routed_postextract.enc.dat]
set output_gif [file join $run_root outputs innovus ${top}_routed.gif]

restoreDesign $checkpoint $top
setLayerPreference pinObj -isVisible 0
setLayerPreference net -isVisible 1
fit
dumpToGIF $output_gif
exit
