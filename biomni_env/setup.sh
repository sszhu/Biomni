#!/bin/bash

# BioAgentOS - Biomni Environment Setup Script
# This script sets up a comprehensive bioinformatics environment with various tools and packages

# Set up colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default tools directory is the current directory
DEFAULT_TOOLS_DIR="$(pwd)/biomni_tools"
TOOLS_DIR=""

echo -e "${YELLOW}=== Biomni Environment Setup ===${NC}"
echo -e "${BLUE}This script will set up a comprehensive bioinformatics environment with various tools and packages.${NC}"

# Paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RESTORE=false
RESTORE_URI=""

# Parse flags
NO_R=false
NO_PYTHON=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-r)
            NO_R=true
            shift
            ;;
        --restore)
            RESTORE=true
            # Optional URI argument (s3:// or cos://)
            if [[ ${2:-} =~ ^s3://|^cos:// ]]; then
                RESTORE_URI="$2"
                shift 2
            else
                shift
            fi
            ;;
        --no-python)
            NO_PYTHON=true
            shift
            ;;
        *)
            # Unknown option; ignore for now
            shift
            ;;
    esac
done

install_micromamba() {
    echo -e "${YELLOW}Installing micromamba...${NC}"
    # Determine platform tag for micromamba (linux-64, linux-aarch64, osx-64, osx-arm64)
    local uname_s uname_m platform_tag
    uname_s=$(uname -s)
    uname_m=$(uname -m)
    case "$uname_s" in
        Linux)
            case "$uname_m" in
                x86_64|amd64)
                    platform_tag="linux-64" ;;
                aarch64|arm64)
                    platform_tag="linux-aarch64" ;;
                *)
                    platform_tag="linux-64" ;;
            esac ;;
        Darwin)
            case "$uname_m" in
                x86_64)
                    platform_tag="osx-64" ;;
                arm64)
                    platform_tag="osx-arm64" ;;
                *)
                    platform_tag="osx-64" ;;
            esac ;;
        *)
            platform_tag="linux-64" ;;
    esac
    local dest_dir="$HOME/.local/bin"
    mkdir -p "$dest_dir"
    # Download and extract micromamba binary
    curl -Ls "https://micro.mamba.pm/api/micromamba/${platform_tag}/latest" | tar -xvj -C "$dest_dir" --strip-components=2 bin/micromamba
    handle_error $? "Failed to download/extract micromamba." false
    export PATH="$dest_dir:$PATH"
    if command -v micromamba &> /dev/null; then
        echo -e "${GREEN}micromamba installed at $(command -v micromamba)${NC}"
    else
        echo -e "${RED}micromamba installation did not succeed.${NC}"
    fi
}

install_uv() {
    echo -e "${YELLOW}Installing uv...${NC}"
    curl -Ls https://astral.sh/uv/install.sh | sh
    # uv installs to ~/.local/bin by default
    export PATH="$HOME/.local/bin:$PATH"
    if command -v uv &> /dev/null; then
        echo -e "${GREEN}uv installed at $(command -v uv)${NC}"
    else
        echo -e "${RED}uv installation did not succeed.${NC}"
    fi
}

# Helper: Update PATH and R_LIBS_USER in shell profile
configure_shell_profile() {
    # Detect shell profile file
    local shell_name
    shell_name=$(basename "$SHELL")
    local profile_file="$HOME/.bashrc"
    if [ "$shell_name" = "zsh" ]; then
        profile_file="$HOME/.zshrc"
    fi

    # Ensure profile file exists
    touch "$profile_file"

    # Configure R_LIBS_USER
    local r_dir="$HOME/.local/R/library"
    local r_line="export R_LIBS_USER=\"$r_dir\""
    mkdir -p "$r_dir"
    if ! grep -q "R_LIBS_USER" "$profile_file"; then
        echo "# Biomni: user R library" >> "$profile_file"
        echo "$r_line" >> "$profile_file"
        echo -e "${GREEN}Added R_LIBS_USER to $profile_file${NC}"
    else
        echo -e "${YELLOW}R_LIBS_USER already set in $profile_file${NC}"
    fi

    # Configure PATH for CLI tools if available
    if [ -n "$TOOLS_DIR" ] && [ -d "$TOOLS_DIR/bin" ]; then
        local path_line="export PATH=\"$TOOLS_DIR/bin:\$PATH\""
        if ! grep -q "biomni_tools/bin" "$profile_file" && ! grep -Fq "$path_line" "$profile_file"; then
            echo "# Biomni: CLI tools path" >> "$profile_file"
            echo "$path_line" >> "$profile_file"
            echo -e "${GREEN}Added CLI tools PATH to $profile_file${NC}"
        else
            echo -e "${YELLOW}CLI tools PATH already present in $profile_file${NC}"
        fi
    fi
}

# Ensure Python is installed in the environment
ensure_python_in_env() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}Python not found in env; installing python=3.11...${NC}"
        micromamba install -y -n biomni_e1 python=3.11
        handle_error $? "Failed to install Python into biomni_e1 environment." false
    fi
}

# Ensure R is installed in the environment
ensure_r_in_env() {
    if ! command -v Rscript &> /dev/null; then
        echo -e "${YELLOW}R not found in env; installing r-base and r-essentials...${NC}"
        micromamba install -y -n biomni_e1 r-base r-essentials
        handle_error $? "Failed to install R into biomni_e1 environment." true
    fi
}

# Ensure micromamba is available
if ! command -v micromamba &> /dev/null; then
    install_micromamba
fi

# Ensure uv is available
if ! command -v uv &> /dev/null; then
    install_uv
fi

# Function to handle errors
handle_error() {
    local exit_code=$1
    local error_message=$2
    local optional=${3:-false}

    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}Error: $error_message${NC}"
        if [ "$optional" = true ]; then
            echo -e "${YELLOW}Continuing with setup as this component is optional.${NC}"
            return 0
        else
            if [ -z "$NON_INTERACTIVE" ]; then
                read -p "Continue with setup? (y/n) " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    echo -e "${RED}Setup aborted.${NC}"
                    exit 1
                fi
            else
                echo -e "${YELLOW}Non-interactive mode: continuing despite error.${NC}"
            fi
        fi
    fi
    return $exit_code
}


# Function to install a specific environment file using micromamba
install_env_file() {
    local env_file=$1
    local description=$2
    local optional=${3:-false}

    echo -e "\n${BLUE}=== Installing $description ===${NC}"

    if [ "$optional" = true ]; then
        if [ -z "$NON_INTERACTIVE" ]; then
            read -p "Do you want to install $description? (y/n) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo -e "${YELLOW}Skipping $description installation.${NC}"
                return 0
            fi
        else
            echo -e "${YELLOW}Non-interactive mode: automatically installing $description.${NC}"
        fi
    fi

    echo -e "${YELLOW}Installing $description from $env_file...${NC}"
    micromamba env update -n biomni_e1 -f $env_file
    handle_error $? "Failed to install $description." $optional

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Successfully installed $description!${NC}"
    fi
}

# Function to install CLI tools
install_cli_tools() {
    echo -e "\n${BLUE}=== Installing Command-Line Bioinformatics Tools ===${NC}"

    # Ask user for the directory to install CLI tools
    if [ -z "$NON_INTERACTIVE" ]; then
        echo -e "${YELLOW}Where would you like to install the command-line tools?${NC}"
        echo -e "${BLUE}Default: $DEFAULT_TOOLS_DIR${NC}"
        read -p "Enter directory path (or press Enter for default): " user_tools_dir
    else
        user_tools_dir=""
        echo -e "${YELLOW}Non-interactive mode: using default directory $DEFAULT_TOOLS_DIR for CLI tools.${NC}"
    fi

    if [ -z "$user_tools_dir" ]; then
        TOOLS_DIR="$DEFAULT_TOOLS_DIR"
    else
        TOOLS_DIR="$user_tools_dir"
    fi

    # Export the tools directory for the CLI tools installer
    export BIOMNI_TOOLS_DIR="$TOOLS_DIR"

    echo -e "${YELLOW}Installing command-line tools (PLINK, IQ-TREE, GCTA, etc.) to $TOOLS_DIR...${NC}"

    # Set environment variable to skip prompts in the CLI tools installer
    export BIOMNI_AUTO_INSTALL=1

    # Run the CLI tools installer
    bash install_cli_tools.sh
    handle_error $? "Failed to install CLI tools." true

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Successfully installed command-line tools!${NC}"

        # Create a setup_path.sh file in the current directory
        echo "#!/bin/bash" > setup_path.sh
        echo "# Added by biomni setup" >> setup_path.sh
        echo "# Remove any old paths first to avoid duplicates" >> setup_path.sh
        echo "PATH=\$(echo \$PATH | tr ':' '\n' | grep -v \"biomni_tools/bin\" | tr '\n' ':' | sed 's/:$//')" >> setup_path.sh
        echo "export PATH=\"$TOOLS_DIR/bin:\$PATH\"" >> setup_path.sh
        chmod +x setup_path.sh

        echo -e "${GREEN}Created setup_path.sh in the current directory.${NC}"
        echo -e "${YELLOW}You can add the tools to your PATH by running:${NC}"
        echo -e "${GREEN}source $(pwd)/setup_path.sh${NC}"

        # Also add to the current session
        # Remove any old paths first to avoid duplicates
        PATH=$(echo $PATH | tr ':' '\n' | grep -v "biomni_tools/bin" | tr '\n' ':' | sed 's/:$//')
        export PATH="$TOOLS_DIR/bin:$PATH"

        # Persist PATH and R library settings in shell profile
        configure_shell_profile
    fi

    # Unset the environment variables
    unset BIOMNI_AUTO_INSTALL
    unset BIOMNI_TOOLS_DIR
}

# Main installation process
main() {

    # Step 1: Create base micromamba environment from merged environment.yml
    echo -e "\n${YELLOW}Step 1: Creating base environment using micromamba...${NC}"
    create_ok=0
    if [ "$NO_R" = true ]; then
        echo -e "${YELLOW}--no-r flag: creating environment via explicit package list (no R).${NC}"
        for attempt in 1 2; do
            micromamba create -y -n biomni_e1 -c conda-forge -c bioconda \
                python=3.11 blast samtools bowtie2 bwa bedtools fastqc trimmomatic mafft gseapy
            if [ $? -eq 0 ]; then
                create_ok=1
                break
            else
                echo -e "${RED}Micromamba create failed (attempt $attempt). Cleaning cache and retrying...${NC}"
                micromamba clean --all -y
            fi
        done
    else
        env_spec_file="environment.yml"
        for attempt in 1 2; do
            micromamba env create -y -n biomni_e1 -f "$env_spec_file"
            if [ $? -eq 0 ]; then
                create_ok=1
                break
            else
                echo -e "${RED}Micromamba env create failed (attempt $attempt). Cleaning cache and retrying...${NC}"
                micromamba clean --all -y
            fi
        done
    fi
    if [ $create_ok -ne 1 ]; then
        echo -e "${YELLOW}Falling back to minimal environment via explicit package list...${NC}"
        micromamba create -y -n biomni_e1 -c conda-forge -c bioconda python=3.11
        handle_error $? "Failed to create micromamba environment in fallback mode."
    fi

    # Step 2: Activate the environment
    echo -e "\n${YELLOW}Step 2: Activating micromamba environment...${NC}"
    # Detect shell for proper hook
    current_shell=$(basename "$SHELL")
    if [ "$current_shell" = "zsh" ]; then
        eval "$(micromamba shell hook --shell zsh)"
    else
        eval "$(micromamba shell hook --shell bash)"
    fi
    micromamba activate biomni_e1
    handle_error $? "Failed to activate biomni_e1 environment."

    # Ensure core runtimes are present
    if [ "$NO_PYTHON" != true ]; then
        ensure_python_in_env
    else
        echo -e "${YELLOW}--no-python flag: skipping Python auto-install.${NC}"
    fi
    if [ "$NO_R" != true ]; then
        ensure_r_in_env
    else
        echo -e "${YELLOW}--no-r flag: skipping R auto-install.${NC}"
    fi

    # Step 3: Install additional R packages through R's package manager (optional)
    echo -e "\n${YELLOW}Step 3: Installing additional R packages through R's package manager...${NC}"
    if [ "$NO_R" = true ]; then
        echo -e "${YELLOW}--no-r flag: skipping optional R package installation.${NC}"
    elif command -v Rscript &> /dev/null; then
        export R_LIBS_USER="$HOME/.local/R/library"
        mkdir -p "$R_LIBS_USER"
        Rscript install_r_packages.R
        handle_error $? "Failed to install additional R packages." true
    else
        echo -e "${YELLOW}Rscript not found in the environment; skipping optional R package installation.${NC}"
    fi

    # Step 4: Install Python packages with uv (if requirements.txt exists)
    if [ -f "requirements.txt" ] && [ "$NO_PYTHON" != true ]; then
        echo -e "\n${YELLOW}Step 4: Installing Python packages with uv...${NC}"
        if command -v python3 &> /dev/null; then
            env_python=$(which python3)
            uv pip install --python "$env_python" -r requirements.txt
            handle_error $? "Failed to install Python packages with uv." false
        else
            echo -e "${RED}Python interpreter not found in the activated environment; skipping uv installation.${NC}"
        fi
    elif [ -f "requirements.txt" ] && [ "$NO_PYTHON" = true ]; then
        echo -e "${YELLOW}--no-python flag: skipping uv Python package installation.${NC}"
    fi

    # Step 5: Install CLI tools
    echo -e "\n${YELLOW}Step 5: Installing command-line bioinformatics tools...${NC}"
    install_cli_tools

    # Setup completed
    echo -e "\n${GREEN}=== Biomni Environment Setup Completed! ===${NC}"
    echo -e "You can now run the example analysis with: ${YELLOW}python bio_analysis_example.py${NC}"
    echo -e "To activate this environment in the future, run: ${YELLOW}micromamba activate biomni_e1${NC}"
    echo -e "To use BioAgentOS, navigate to the BioAgentOS directory and follow the instructions in the README."

    # Display CLI tools setup instructions
    if [ -n "$TOOLS_DIR" ]; then
        echo -e "\n${BLUE}=== Command-Line Tools Setup ===${NC}"
        echo -e "The command-line tools are installed in: ${YELLOW}$TOOLS_DIR${NC}"
        echo -e "To add these tools to your PATH, run: ${YELLOW}source $(pwd)/setup_path.sh${NC}"
        echo -e "You can also add this line to your shell profile for permanent access:"
        echo -e "${GREEN}export PATH=\"$TOOLS_DIR/bin:\$PATH\"${NC}"

        # Test if tools are accessible
        echo -e "\n${BLUE}=== Testing CLI Tools ===${NC}"
        if command -v plink2 &> /dev/null; then
            echo -e "${GREEN}PLINK2 is accessible in the current PATH${NC}"
            echo -e "PLINK2 location: $(which plink2)"
        else
            echo -e "${RED}PLINK2 is not accessible in the current PATH${NC}"
            echo -e "Please run: ${YELLOW}source $(pwd)/setup_path.sh${NC} to update your PATH"
        fi

        if command -v gcta64 &> /dev/null; then
            echo -e "${GREEN}GCTA is accessible in the current PATH${NC}"
            echo -e "GCTA location: $(which gcta64)"
        else
            echo -e "${RED}GCTA is not accessible in the current PATH${NC}"
            echo -e "Please run: ${YELLOW}source $(pwd)/setup_path.sh${NC} to update your PATH"
        fi

        if command -v iqtree2 &> /dev/null; then
            echo -e "${GREEN}IQ-TREE is accessible in the current PATH${NC}"
            echo -e "IQ-TREE location: $(which iqtree2)"
        else
            echo -e "${RED}IQ-TREE is not accessible in the current PATH${NC}"
            echo -e "Please run: ${YELLOW}source $(pwd)/setup_path.sh${NC} to update your PATH"
        fi
    fi

    PATH=$(echo $PATH | tr ':' '\n' | grep -v "biomni_tools/bin" | tr '\n' ':' | sed 's/:$//')
    export PATH="$(pwd)/biomni_tools/bin:$PATH"

    # Finalize shell profile configuration (ensures R_LIBS_USER is set even if CLI tools skipped)
    configure_shell_profile

    # If repo root has no top-level data directory, attempt automatic restore using defaults
    if [ ! -d "$REPO_ROOT/data" ]; then
        echo -e "\n${YELLOW}No top-level 'data' directory found in repo root (${REPO_ROOT}). Attempting restore...${NC}"
        if [ -f "$REPO_ROOT/data_backup_restore.sh" ]; then
            (cd "$REPO_ROOT" && bash ./data_backup_restore.sh restore) || echo -e "${RED}Automatic restore failed. You can run it manually from ${REPO_ROOT}.${NC}"
        else
            echo -e "${RED}data_backup_restore.sh not found in repo root; skipping auto-restore.${NC}"
        fi
    fi

    # If --restore was provided, force a restore now (overrides presence of data dir)
    if [ "$RESTORE" = true ]; then
        echo -e "\n${YELLOW}--restore flag detected: running data restore from repo root...${NC}"
        if [ -f "$REPO_ROOT/data_backup_restore.sh" ]; then
            if [ -n "$RESTORE_URI" ]; then
                (cd "$REPO_ROOT" && bash ./data_backup_restore.sh restore "$RESTORE_URI") || echo -e "${RED}Explicit restore failed. Please rerun manually.${NC}"
            else
                (cd "$REPO_ROOT" && bash ./data_backup_restore.sh restore) || echo -e "${RED}Restore failed. Please rerun manually.${NC}"
            fi
        else
            echo -e "${RED}data_backup_restore.sh not found in repo root; cannot perform --restore.${NC}"
        fi
    fi
}

# Run the main installation process
main
