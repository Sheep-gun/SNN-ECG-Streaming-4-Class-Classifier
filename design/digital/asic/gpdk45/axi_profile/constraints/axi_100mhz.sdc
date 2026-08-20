create_clock -name axi_core_clk -period 10.000 [get_ports s_axi_aclk]
set_clock_transition 0.100 [get_clocks axi_core_clk]
set_clock_uncertainty -setup 0.200 [get_clocks axi_core_clk]
set_clock_uncertainty -hold 0.100 [get_clocks axi_core_clk]

set nonclock_inputs [remove_from_collection [all_inputs] [get_ports s_axi_aclk]]
set timed_inputs [remove_from_collection $nonclock_inputs [get_ports s_axi_aresetn]]
set_input_delay 1.000 -clock axi_core_clk $timed_inputs
set_input_transition 0.100 $timed_inputs
set_false_path -from [get_ports s_axi_aresetn]

set_output_delay 1.000 -clock axi_core_clk [all_outputs]
set_load 0.020 [all_outputs]
