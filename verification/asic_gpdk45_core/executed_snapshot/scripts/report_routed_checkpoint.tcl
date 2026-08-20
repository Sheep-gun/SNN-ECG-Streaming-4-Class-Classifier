foreach required_env {RUN_ROOT} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set run_root [file normalize $::env(RUN_ROOT)]
set top snn_ecg_asic_core_top
set report_dir [file join $run_root reports innovus]
set output_dir [file join $run_root outputs innovus]
set checkpoint [file join $output_dir ${top}_routed_preextract.enc.dat]

file mkdir $report_dir
file mkdir $output_dir

setMultiCpuUsage -localCpu 8
restoreDesign $checkpoint $top

setExtractRCMode -engine postRoute -effortLevel high -coupled true
extractRC
set extraction_log [open [file join $report_dir extraction_engine.txt] w]
puts $extraction_log "engine=IQuantus high effort"
puts $extraction_log "status=0"
close $extraction_log

saveDesign [file join $output_dir ${top}_routed_postextract.enc]
timeDesign -postRoute -outDir [file join $report_dir time_design_setup]
timeDesign -postRoute -hold -outDir [file join $report_dir time_design_hold]
report_timing -view setup_slow -late -max_paths 50 > [file join $report_dir timing_postroute_setup.rpt]
report_timing -view hold_fast -early -max_paths 50 > [file join $report_dir timing_postroute_hold.rpt]
report_area > [file join $report_dir area_postroute.rpt]
report_ccopt_clock_trees -file [file join $report_dir ccopt_clock_trees.rpt]
report_ccopt_skew_groups -file [file join $report_dir ccopt_skew_groups.rpt]
verifyConnectivity -type regular -report [file join $report_dir connectivity_signal_postroute.rpt]

set power_status [catch {
    set_default_switching_activity -input_activity 0.10 -seq_activity 0.10
    report_power > [file join $report_dir power_postroute_vectorless.rpt]
} power_message]
set power_log [open [file join $report_dir power_command_status.txt] w]
puts $power_log "status=$power_status"
puts $power_log $power_message
close $power_log

defOut -netlist -floorplan -routing [file join $output_dir ${top}_routed.def]
saveNetlist [file join $output_dir ${top}_postroute.v]
write_sdf \
    -max_view setup_slow \
    -min_view hold_fast \
    -version 3.0 \
    [file join $output_dir ${top}_postroute.sdf]
rcOut -rc_corner max_rc -spef [file join $output_dir ${top}_postroute_max_rc.spef]
rcOut -rc_corner min_rc -spef [file join $output_dir ${top}_postroute_min_rc.spef]

exit
