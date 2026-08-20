if {![info exists ::env(RUN_ROOT)]} {
    error "Missing required environment variable: RUN_ROOT"
}

set run_root [file normalize $::env(RUN_ROOT)]
set profile core
if {[info exists ::env(ASIC_PROFILE)]} {
    set profile [string tolower [string trim $::env(ASIC_PROFILE)]]
}
switch -- $profile {
    core { set top snn_ecg_asic_core_top }
    axi { set top snn_ecg_axi_asic_top }
    default { error "ASIC_PROFILE must be core or axi, got: $profile" }
}

set report_dir [file join $run_root reports innovus_pg]
set output_dir [file join $run_root outputs innovus_pg]
set checkpoint [file join $run_root outputs innovus ${top}_routed.enc.dat]
if {[info exists ::env(PG_INPUT_CHECKPOINT)]} {
    set checkpoint [file normalize $::env(PG_INPUT_CHECKPOINT)]
}
file mkdir $report_dir
file mkdir $output_dir

# Geometry-only engineering assumptions. They are not derived from IR/EM or a
# foundry current-density deck and must not be described as signoff PG sizing.
set ring_width 1.00
set ring_spacing 0.50
set ring_offset 2.00
set stripe_width 0.80
set stripe_spacing 0.40
set stripe_pitch 40.00

restoreDesign $checkpoint $top
globalNetConnect VDD -type pgpin -pin VDD -all
globalNetConnect VSS -type pgpin -pin VSS -all

addRing -nets {VDD VSS} -type core_rings -follow core \
    -layer {top Metal5 bottom Metal5 left Metal6 right Metal6} \
    -width $ring_width -spacing $ring_spacing -offset $ring_offset
addStripe -nets {VDD VSS} -layer Metal6 -direction vertical \
    -width $stripe_width -spacing $stripe_spacing \
    -set_to_set_distance $stripe_pitch
sroute -nets {VDD VSS} \
    -connect {corePin floatingStripe} \
    -allowJogging 1 -allowLayerChange 1 \
    -layerChangeRange {Metal1 Metal6} \
    -targetViaLayerRange {Metal1 Metal6}

set filler_cells [dbGet head.allCells.name FILL*]
if {[llength $filler_cells] == 0} {
    error "No FILL* cell masters are available"
}
setFillerMode -core $filler_cells -corePrefix FILL -fitGap true
addFiller
checkFiller > [file join $report_dir check_filler.rpt]
checkPlace > [file join $report_dir check_place.rpt]
verifyConnectivity -type special -report [file join $report_dir connectivity_pg.rpt]
verifyConnectivity -type regular -report [file join $report_dir connectivity_signal.rpt]
verifyGeometry > [file join $report_dir geometry_internal.rpt]
report_area > [file join $report_dir area_with_fillers.rpt]

saveDesign [file join $output_dir ${top}_pg_fillers.enc]
defOut -netlist -floorplan -routing \
    [file join $output_dir ${top}_pg_fillers.def]

set status_file [open [file join $report_dir pg_assumptions.txt] w]
puts $status_file "scope=exploratory geometry only"
puts $status_file "ring_width_um=$ring_width"
puts $status_file "ring_spacing_um=$ring_spacing"
puts $status_file "ring_offset_um=$ring_offset"
puts $status_file "stripe_width_um=$stripe_width"
puts $status_file "stripe_spacing_um=$stripe_spacing"
puts $status_file "stripe_pitch_um=$stripe_pitch"
puts $status_file "ir_em_analyzed=false"
puts $status_file "top_pg_pads_or_sources=false"
puts $status_file "tap_endcap_available=false"
puts $status_file "decap_and_metal_fill_inserted=false"
close $status_file

exit
