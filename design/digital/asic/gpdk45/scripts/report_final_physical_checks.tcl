foreach required_env {RUN_ROOT FINAL_CHECKPOINT FINAL_TAG} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set run_root [file normalize $::env(RUN_ROOT)]
set tag $::env(FINAL_TAG)
set profile core
if {[info exists ::env(ASIC_PROFILE)]} {
    set profile [string tolower [string trim $::env(ASIC_PROFILE)]]
}
switch -- $profile {
    core { set top snn_ecg_asic_core_top }
    axi { set top snn_ecg_axi_asic_top }
    default { error "ASIC_PROFILE must be core or axi, got: $profile" }
}

set report_dir [file join $run_root reports final_checks $tag]
file mkdir $report_dir
restoreDesign [file normalize $::env(FINAL_CHECKPOINT)] $top
setAnalysisMode -analysisType onChipVariation -cppr both
setDelayCalMode -SIAware true

# Validate the realized tree against the documented 60 ps engineering target.
set_ccopt_property -net_type top target_max_trans 60ps
set_ccopt_property -net_type trunk target_max_trans 60ps
set_ccopt_property -net_type leaf target_max_trans 60ps
report_ccopt_clock_trees -file [file join $report_dir ccopt_clock_trees_60ps.rpt]
report_ccopt_skew_groups -file [file join $report_dir ccopt_skew_groups.rpt]

verify_drc -report [file join $report_dir internal_route_drc.rpt]
verifyConnectivity -type regular -report [file join $report_dir connectivity_signal.rpt]
checkPlace > [file join $report_dir check_place.rpt]
exit
