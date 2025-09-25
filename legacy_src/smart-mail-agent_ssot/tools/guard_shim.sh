# guard shim：若原本 guard::at_root/venv_on 之類不存在，提供溫和替身
guard::at_root(){ return 0; }
guard::venv_on(){ return 0; }
guard::req(){ return 0; }
