foreach required_env {RUN_ROOT INPUT_CHECKPOINT ASIC_PROFILE HOLD_TAG} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set run_root [file normalize $::env(RUN_ROOT)]
set checkpoint [file normalize $::env(INPUT_CHECKPOINT)]
set profile [string tolower [string trim $::env(ASIC_PROFILE)]]
set tag [string trim $::env(HOLD_TAG)]
switch -- $profile {
    core { set top snn_ecg_asic_core_top }
    axi { set top snn_ecg_axi_asic_top }
    default { error "ASIC_PROFILE must be core or axi, got: $profile" }
}

set report_dir [file join $run_root reports hold_baseline $profile $tag]
file mkdir $report_dir
setMultiCpuUsage -localCpu 8
set restore_db_file_check 0
restoreDesign $checkpoint $top
setAnalysisMode -analysisType onChipVariation -cppr both
setDelayCalMode -SIAware true
setExtractRCMode -engine postRoute -effortLevel high -coupled true
extractRC

timeDesign -postRoute -outDir [file join $report_dir time_design_setup]
timeDesign -postRoute -hold -outDir [file join $report_dir time_design_hold]
report_timing -view setup_slow -late -max_paths 200 \
    > [file join $report_dir timing_setup.rpt]
report_timing -view hold_fast -early -max_paths 1000 \
    > [file join $report_dir timing_hold.rpt]

set config [open [file join $report_dir run_config.txt] w]
puts $config "profile=$profile"
puts $config "top=$top"
puts $config "input_checkpoint=$checkpoint"
puts $config "ocv_and_hold_uncertainty=preserved_from_checkpoint"
puts $config "generated_rc_model_cache=excluded_then_high_effort_reextracted"
close $config
exit
