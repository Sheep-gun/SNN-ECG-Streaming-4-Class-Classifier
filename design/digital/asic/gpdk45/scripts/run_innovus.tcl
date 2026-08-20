foreach required_env {RUN_ROOT PDK_ROOT} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

proc env_flag {name default_value} {
    if {![info exists ::env($name)]} {
        return $default_value
    }

    set value [string tolower [string trim $::env($name)]]
    switch -- $value {
        1 - true - yes - on {
            return 1
        }
        0 - false - no - off {
            return 0
        }
        default {
            error "Environment variable $name must be a boolean value, got: $::env($name)"
        }
    }
}

set script_dir [file dirname [file normalize [info script]]]
set run_root [file normalize $::env(RUN_ROOT)]
set pdk_root [file normalize $::env(PDK_ROOT)]
set top snn_ecg_asic_core_top
set report_dir [file join $run_root reports innovus]
set output_dir [file join $run_root outputs innovus]
set tech_lef [file join $pdk_root lef gsclib045_tech.lef]
set macro_lef [file join $pdk_root lef gsclib045_macro.lef]
set mapped_netlist [file join $run_root outputs genus ${top}_mapped.v]
set run_postroute_opt [env_flag RUN_POSTROUTE_OPT 0]
set run_timedesign [env_flag RUN_TIMEDESIGN 0]

file mkdir $report_dir
file mkdir $output_dir

setMultiCpuUsage -localCpu 8
set init_top_cell $top
set init_design_uniquify 1
set init_mmmc_file [file join $script_dir mmmc.tcl]
set init_lef_file [list $tech_lef $macro_lef]
set init_verilog $mapped_netlist
set init_pwr_net VDD
set init_gnd_net VSS
init_design

globalNetConnect VDD -type pgpin -pin VDD -all
globalNetConnect VSS -type pgpin -pin VSS -all
setDesignMode -process 45

floorPlan -site CoreSite -su 1.0 0.65 20 20 20 20 -coreMarginsBy die
createRow -site CoreSiteDouble
assignIoPins -pin *
checkDesign -all > [file join $report_dir check_design_init.rpt]

placeDesign
optDesign -preCTS
report_timing -max_paths 20 > [file join $report_dir timing_postplace.rpt]
report_area > [file join $report_dir area_postplace.rpt]
saveDesign [file join $output_dir ${top}_postplace.enc]

set_ccopt_property buffer_cells {CLKBUFX2 CLKBUFX3 CLKBUFX4 CLKBUFX6 CLKBUFX8 CLKBUFX12}
set_ccopt_property inverter_cells {CLKINVX1 CLKINVX2 CLKINVX3 CLKINVX4 CLKINVX6 CLKINVX8}
set ccopt_spec [file join $output_dir ccopt.spec]
create_ccopt_clock_tree_spec -file $ccopt_spec
source $ccopt_spec
clock_opt_design
optDesign -postCTS
report_timing -max_paths 20 > [file join $report_dir timing_postcts.rpt]
report_ccopt_clock_trees -file [file join $report_dir ccopt_clock_trees.rpt]
report_ccopt_skew_groups -file [file join $report_dir ccopt_skew_groups.rpt]

setNanoRouteMode -routeWithTimingDriven true
setNanoRouteMode -routeWithSiDriven true
routeDesign
saveDesign [file join $output_dir ${top}_routed_preextract.enc]
defOut -netlist -floorplan -routing [file join $output_dir ${top}_routed_preextract.def]

# The reproducible baseline is the routed design with high-effort post-route
# extraction. Do not silently substitute another extraction engine: a failed
# high-effort extraction means that this baseline was not produced.
set extraction_status [catch {
    setExtractRCMode -engine postRoute -effortLevel high -coupled true
    extractRC
} extraction_message]
set extraction_log [open [file join $report_dir extraction_engine.txt] w]
puts $extraction_log "requested_engine=IQuantus high effort"
puts $extraction_log "status=$extraction_status"
puts $extraction_log $extraction_message
close $extraction_log
if {$extraction_status != 0} {
    error "High-effort post-route extraction failed: $extraction_message"
}

# Preserve the routed geometry before any optional optimization or reporting
# command. Innovus does not save the in-memory RCDB here, so every restore below
# explicitly reruns high-effort extraction before producing reports.
set baseline_checkpoint [file join $output_dir ${top}_routed_postextract.enc]
set baseline_restore_db "${baseline_checkpoint}.dat"
saveDesign $baseline_checkpoint
defOut -netlist -floorplan -routing [file join $output_dir ${top}_routed_checkpoint.def]
saveNetlist [file join $output_dir ${top}_postroute_checkpoint.v]

# Post-route optimization is opt-in because it is unavailable in the observed
# limited Non-OCV MMMC execution path. If an opt-in attempt fails, restore the
# extracted routed baseline so that subsequent reports remain reproducible.
set setup_opt_status "skipped"
set setup_opt_message "RUN_POSTROUTE_OPT=0"
set hold_opt_status "skipped"
set hold_opt_message "RUN_POSTROUTE_OPT=0"
set reextract_status "skipped"
set reextract_message "RUN_POSTROUTE_OPT=0"
set baseline_restore_reextract_status "not_needed"
set baseline_restore_reextract_message "RUN_POSTROUTE_OPT=0"
set reported_design "routed_high_effort_extracted_baseline"

if {$run_postroute_opt} {
    set setup_opt_status [catch {
        optDesign -postRoute
    } setup_opt_message]

    if {$setup_opt_status == 0} {
        set hold_opt_status [catch {
            optDesign -postRoute -hold
        } hold_opt_message]
    } else {
        set hold_opt_status "skipped"
        set hold_opt_message "setup optimization failed"
    }

    if {($setup_opt_status == 0) && ($hold_opt_status == 0)} {
        set reextract_status [catch {
            setExtractRCMode -engine postRoute -effortLevel high -coupled true
            extractRC
        } reextract_message]
    } else {
        set reextract_status "skipped"
        set reextract_message "optimization failed"
    }

    if {($setup_opt_status == 0) && ($hold_opt_status == 0) && ($reextract_status == 0)} {
        set reported_design "postroute_optimized_high_effort_reextracted"
    } else {
        set baseline_restore_reextract_status [catch {
            restoreDesign $baseline_restore_db $top
            setExtractRCMode -engine postRoute -effortLevel high -coupled true
            extractRC
        } baseline_restore_reextract_message]
        if {$baseline_restore_reextract_status != 0} {
            error "Failed to restore and re-extract routed baseline: $baseline_restore_reextract_message"
        }
        set reported_design "restored_routed_high_effort_reextracted_baseline"
    }
}

set opt_log [open [file join $report_dir postroute_optimization_status.txt] w]
puts $opt_log "run_postroute_opt=$run_postroute_opt"
puts $opt_log "setup_status=$setup_opt_status"
puts $opt_log "setup_message=$setup_opt_message"
puts $opt_log "hold_status=$hold_opt_status"
puts $opt_log "hold_message=$hold_opt_message"
puts $opt_log "reextract_status=$reextract_status"
puts $opt_log "reextract_message=$reextract_message"
puts $opt_log "baseline_restore_reextract_status=$baseline_restore_reextract_status"
puts $opt_log "baseline_restore_reextract_message=$baseline_restore_reextract_message"
puts $opt_log "reported_design=$reported_design"
puts $opt_log "hold_closure_claim=not_established"
close $opt_log

# timeDesign uses the same unavailable Non-OCV optimization/signoff path in the
# observed environment, so it is separately opt-in and never gates the baseline
# reports below.
set timed_setup_status "skipped"
set timed_setup_message "RUN_TIMEDESIGN=0"
set timed_hold_status "skipped"
set timed_hold_message "RUN_TIMEDESIGN=0"
if {$run_timedesign} {
    set timed_setup_status [catch {
        timeDesign -postRoute -outDir [file join $report_dir time_design_setup]
    } timed_setup_message]
    set timed_hold_status [catch {
        timeDesign -postRoute -hold -outDir [file join $report_dir time_design_hold]
    } timed_hold_message]
}

set timed_log [open [file join $report_dir time_design_status.txt] w]
puts $timed_log "run_timedesign=$run_timedesign"
puts $timed_log "setup_status=$timed_setup_status"
puts $timed_log "setup_message=$timed_setup_message"
puts $timed_log "hold_status=$timed_hold_status"
puts $timed_log "hold_message=$timed_hold_message"
close $timed_log

# Explicit reports and exports are the baseline PPA evidence. A hold report is
# an observation of the routed design, not proof that hold timing was closed.
setDelayCalMode -SIAware true
report_timing -view setup_slow -late -max_paths 50 > [file join $report_dir timing_postroute_setup.rpt]
report_timing -view hold_fast -early -max_paths 50 > [file join $report_dir timing_postroute_hold.rpt]
report_area > [file join $report_dir area_postroute.rpt]
verifyConnectivity -type regular -report [file join $report_dir connectivity_signal_postroute.rpt]

# Preserve the reported database before optional power and format exports.
# This core-only study does not build a VDD/VSS ring or stripe network.
saveDesign [file join $output_dir ${top}_reported_postextract.enc]

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
    -recompute_delay_calc \
    -version 3.0 \
    [file join $output_dir ${top}_postroute.sdf]
rcOut -rc_corner max_rc -spef [file join $output_dir ${top}_postroute_max_rc.spef]
rcOut -rc_corner min_rc -spef [file join $output_dir ${top}_postroute_min_rc.spef]
saveDesign [file join $output_dir ${top}_routed.enc]

exit
