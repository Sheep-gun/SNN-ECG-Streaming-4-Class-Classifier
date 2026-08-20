foreach required_env {DUMP_PATH DUMP_SCOPE} {
    if {![info exists ::env($required_env)]} {
        error "Missing required environment variable: $required_env"
    }
}

# The xrun elaboration must use -access +rwc. Without it, optimized design
# nets/ports are absent and the SAIF can misleadingly contain only bound
# diagnostic variables.

set output_path [file normalize $::env(DUMP_PATH)]
set dump_scope $::env(DUMP_SCOPE)

dumpsaif -overwrite -scope $dump_scope \
    -internal -memories -inctoggle -hierarchy -eot \
    -output $output_path
run
exit
