if {![info exists ::env(RUN_ROOT)]} {
    error "RUN_ROOT must point to the extracted run directory"
}

set run_root $::env(RUN_ROOT)
set profile core
if {[info exists ::env(ASIC_PROFILE)]} {
    set profile [string tolower [string trim $::env(ASIC_PROFILE)]]
}
switch -- $profile {
    core { set top snn_ecg_asic_core_top }
    axi { set top snn_ecg_axi_asic_top }
    default { error "ASIC_PROFILE must be core or axi, got: $profile" }
}
set checkpoint [file join $run_root outputs innovus ${top}_routed_postextract.enc.dat]
if {[info exists ::env(LAYOUT_CHECKPOINT)]} {
    set checkpoint [file normalize $::env(LAYOUT_CHECKPOINT)]
}
set tag routed
if {[info exists ::env(LAYOUT_TAG)]} {
    set tag [string trim $::env(LAYOUT_TAG)]
}
set output_gif [file join $run_root outputs innovus ${top}_${tag}.gif]

restoreDesign $checkpoint $top
setLayerPreference pinObj -isVisible 0
setLayerPreference net -isVisible 1
fit
dumpToGIF $output_gif
exit
