foreach required_env {RUN_ROOT PDK_ROOT} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

set run_root [file normalize $::env(RUN_ROOT)]
set pdk_root [file normalize $::env(PDK_ROOT)]
set slow_lib [file join $pdk_root timing slow_vdd1v2_basicCells.lib]
set fast_lib [file join $pdk_root timing fast_vdd1v2_basicCells.lib]
set qrc_tech [file join $pdk_root qrc qx gpdk045.tch]
set mapped_sdc [file join $run_root outputs genus snn_ecg_asic_core_top_mapped.sdc]

create_library_set -name slow_libset -timing [list $slow_lib]
create_library_set -name fast_libset -timing [list $fast_lib]

create_rc_corner -name max_rc \
    -temperature 125.0 \
    -qx_tech_file $qrc_tech \
    -pre_route_res 1.0 \
    -pre_route_cap 1.0 \
    -pre_route_clock_res 0.0 \
    -pre_route_clock_cap 0.0 \
    -post_route_res {1.0 1.0 1.0} \
    -post_route_cap {1.0 1.0 1.0} \
    -post_route_cross_cap {1.0 1.0 1.0} \
    -post_route_clock_res {1.0 1.0 1.0} \
    -post_route_clock_cap {1.0 1.0 1.0}

create_rc_corner -name min_rc \
    -temperature 0.0 \
    -qx_tech_file $qrc_tech \
    -pre_route_res 1.0 \
    -pre_route_cap 1.0 \
    -pre_route_clock_res 0.0 \
    -pre_route_clock_cap 0.0 \
    -post_route_res {1.0 1.0 1.0} \
    -post_route_cap {1.0 1.0 1.0} \
    -post_route_cross_cap {1.0 1.0 1.0} \
    -post_route_clock_res {1.0 1.0 1.0} \
    -post_route_clock_cap {1.0 1.0 1.0}

create_delay_corner -name slow_delay -library_set slow_libset -rc_corner max_rc
create_delay_corner -name fast_delay -library_set fast_libset -rc_corner min_rc
create_constraint_mode -name functional -sdc_files [list $mapped_sdc]
create_analysis_view -name setup_slow -constraint_mode functional -delay_corner slow_delay
create_analysis_view -name hold_fast -constraint_mode functional -delay_corner fast_delay

set_analysis_view \
    -setup {setup_slow} \
    -hold {hold_fast} \
    -leakage {setup_slow} \
    -dynamic {setup_slow}
