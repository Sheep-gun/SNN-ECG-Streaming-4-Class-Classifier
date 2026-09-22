// Isolated variable-length runner; legacy arithmetic/source remains unchanged.
#include "exact_model.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
int main(int argc,char** argv) try {
    if(argc!=4)throw std::runtime_error("usage: extract_snapshots input.hex output.csv N");
    int n=std::stoi(argv[3]); if(n!=5&&n!=10&&n!=30)throw std::runtime_error("N not registered");
    std::ifstream in(argv[1],std::ios::binary); if(!in)throw std::runtime_error("input open");
    std::ofstream out(argv[2],std::ios::binary);if(!out)throw std::runtime_error("output open");
    out<<"snapshot_index,accepted_samples,beat_count,pnn_match_count,pnn_mismatch_count,dscr_flip_count,dscr_slope_count,ram_code_sum,ram_code_count,rdm_valid_count,rdm_code_sum,ectopic_pair_count,qrs_maf_count,qrs_width_abn_count,qrs_complex_abn_count,qrs_energy_abn_count,rbbb_delay_like_count,pre_qrs_bump_count\n";
    snn::SnapshotFrontEnd f;char b[4];int raw_count=0,index=0,accepted=0,within=0;
    auto nib=[](char c)->int {if(c>='0'&&c<='9')return c-'0';if(c>='A'&&c<='F')return c-'A'+10;throw std::runtime_error("hex format");};
    while(in.read(b,4)) {
        if(b[3]!='\n')throw std::runtime_error("LF hex contract");
        int raw=16*16*nib(b[0])+16*nib(b[1])+nib(b[2]);
        if(++raw_count<=5000)continue;
        if(index>=n)throw std::runtime_error("extra samples");
        if(within==0){f.reset();f.tick(false,false,true,false,0);}
        f.tick(true,true,false,false,static_cast<std::int16_t>(raw-2048));++accepted;++within;
        if(within!=60000){f.tick(false,false,false,false,0);f.tick(false,false,false,false,0);continue;}
        f.tick(false,false,false,true,0);for(int i=0;i<36;++i)f.tick(false,false,false,false,0);
        const auto s=f.finish(index,accepted);
        out<<s.snapshot_index<<','<<s.accepted_samples<<','<<s.beat_count<<','<<s.pnn_match_count<<','<<s.pnn_mismatch_count
        <<','<<s.dscr_flip_count<<','<<s.dscr_slope_count<<','<<s.ram_code_sum<<','<<s.ram_code_count
        <<','<<s.rdm_valid_count<<','<<s.rdm_code_sum<<','<<s.ectopic_pair_count<<','<<s.qrs_maf_count
        <<','<<s.qrs_width_abn_count<<','<<s.qrs_complex_abn_count<<','<<s.qrs_energy_abn_count
        <<','<<s.rbbb_delay_like_count<<','<<s.pre_qrs_bump_count<<'\n';
        ++index;within=0;
    }
    if(in.gcount()!=0||raw_count!=5000+60000*n||accepted!=60000*n||index!=n||within)throw std::runtime_error("count contract");
    out.close();if(!out)throw std::runtime_error("output write");
    std::cout<<"PASS raw="<<raw_count<<" accepted="<<accepted<<" snapshots="<<index<<" legacy_prediction_unused=1\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
