if {![info exists repo_root]} {
    error "repo_root must be set before sourcing rtl_files.tcl"
}

set rtl_root [file join $repo_root design digital rtl]
set asic_root [file join $repo_root design digital asic gpdk45]

set rtl_files [list \
    [file join $rtl_root core abandoned_feature_stubs.v] \
    [file join $rtl_root core class_score_neurons.v] \
    [file join $rtl_root core dscr_spike_counter.v] \
    [file join $rtl_root core ecg_event_encoder_adaptive.v] \
    [file join $rtl_root core ectopic_pair_neuron.v] \
    [file join $rtl_root core pnn_rhythm_predictor.v] \
    [file join $rtl_root core qrs_lif_detector.v] \
    [file join $rtl_root core qrs_maf_neuron.v] \
    [file join $rtl_root core ram_peak_accumulator.v] \
    [file join $rtl_root core rbbb_qrs_delay_bank.v] \
    [file join $rtl_root core rdm_variability_neuron.v] \
    [file join $rtl_root core snn_ecg_3feat_top.v] \
    [file join $rtl_root core snn_ecg_input_normalizer.v] \
    [file join $rtl_root final_membrane_layer.v] \
    [file join $rtl_root snn_ecg_30min_final_top.v] \
    [file join $asic_root rtl snn_ecg_asic_core_top.v]]

set rtl_include_dirs [list $rtl_root [file join $rtl_root core]]
