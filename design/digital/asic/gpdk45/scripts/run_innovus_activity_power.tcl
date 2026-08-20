foreach required_env {RUN_ROOT ACTIVITY_FILE ACTIVITY_TAG} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
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

set tag $::env(ACTIVITY_TAG)
set activity_format SAIF
if {[info exists ::env(ACTIVITY_FORMAT)]} {
    set activity_format [string toupper [string trim $::env(ACTIVITY_FORMAT)]]
}
set report_dir [file join $run_root reports activity_power $tag]
set checkpoint [file join $run_root outputs innovus ${top}_routed.enc.dat]
if {[info exists ::env(ACTIVITY_CHECKPOINT)]} {
    set checkpoint [file normalize $::env(ACTIVITY_CHECKPOINT)]
}
file mkdir $report_dir

if {![file exists $checkpoint]} {
    error "Activity checkpoint does not exist: $checkpoint"
}

restoreDesign $checkpoint $top
setAnalysisMode -analysisType onChipVariation -cppr both
setDelayCalMode -SIAware true
setExtractRCMode -engine postRoute -effortLevel high -coupled true
set extraction_status [catch {extractRC} extraction_message]
if {$extraction_status != 0} {
    error "High-effort activity-power re-extraction failed: $extraction_message"
}
read_activity_file -reset
# Do not let the checkpoint's historical 0.10 vectorless fallback mask missing
# waveform annotation. Clock activity remains defined by the timing clock; all
# other activity must come from the SAIF or propagation from annotated nets.
set_default_switching_activity -input_activity 0.0 -seq_activity 0.0
set_power_analysis_mode -report_missing_nets true
set activity_file [file normalize $::env(ACTIVITY_FILE)]
set activity_scope {}
if {[info exists ::env(ACTIVITY_SCOPE)]} {
    set activity_scope [string trim $::env(ACTIVITY_SCOPE)]
}
if {$activity_scope ne {}} {
    read_activity_file -format $activity_format \
        -scope $activity_scope -block $top \
        -zero_delay true $activity_file \
        > [file join $report_dir activity_annotation.rpt]
} else {
    read_activity_file -format $activity_format \
        -zero_delay true $activity_file \
        > [file join $report_dir activity_annotation.rpt]
}
set missing_net_status [catch {
    dump_unannotated_nets \
        -file [file join $report_dir unannotated_nets.rpt] \
        -type annotationType saif
} missing_net_message]

set power_status [catch {
    report_power -view setup_slow -format detailed \
        > [file join $report_dir power_detailed.rpt]
    report_power -view setup_slow -net -nworst 100 -toggle_rate \
        > [file join $report_dir power_top_switching_nets.rpt]
    report_power -view setup_slow -hierarchy all \
        > [file join $report_dir power_hierarchy.rpt]
} power_message]

set status_file [open [file join $report_dir activity_power_status.txt] w]
puts $status_file "status=$power_status"
puts $status_file "profile=$profile"
puts $status_file "checkpoint=$checkpoint"
puts $status_file "extraction=IQuantus_postRoute_high_coupled"
puts $status_file "extraction_status=$extraction_status"
puts $status_file "activity_file=$::env(ACTIVITY_FILE)"
puts $status_file "activity_format=$activity_format"
puts $status_file "activity_scope=$activity_scope"
puts $status_file "activity_delay_model=zero"
puts $status_file "unannotated_default_activity=0.0"
puts $status_file "unannotated_report_status=$missing_net_status"
puts $status_file "unannotated_report_message=$missing_net_message"
puts $status_file $power_message
close $status_file

if {$power_status != 0} {
    error "Activity-based power reporting failed: $power_message"
}
exit
