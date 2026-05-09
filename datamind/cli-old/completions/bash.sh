#!/bin/bash
# Datamind/datamind/cli/completions/bash.sh

_datamind_completion() {
    local cur prev words cword
    _init_completion || return

    # 基础命令
    local commands="model audit config health version"

    # 子命令补全
    case "${prev}" in
        model)
            local model_commands="list show register activate deactivate promote load unload history params update-params"
            COMPREPLY=($(compgen -W "${model_commands}" -- "${cur}"))
            return
            ;;
        audit)
            local audit_commands="list show export"
            COMPREPLY=($(compgen -W "${audit_commands}" -- "${cur}"))
            return
            ;;
        config)
            local config_commands="show get validate env reload"
            COMPREPLY=($(compgen -W "${config_commands}" -- "${cur}"))
            return
            ;;
        health)
            local health_commands="check db redis all"
            COMPREPLY=($(compgen -W "${health_commands}" -- "${cur}"))
            return
            ;;
        version)
            local version_commands="show check"
            COMPREPLY=($(compgen -W "${version_commands}" -- "${cur}"))
            return
            ;;
    esac

    # 选项补全
    case "${cur}" in
        -*)
            local opts="--help --config --env --debug --version"
            COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
            return
            ;;
        *)
            COMPREPLY=($(compgen -W "${commands}" -- "${cur}"))
            return
            ;;
    esac
}

complete -F _datamind_completion datamind