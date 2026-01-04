#!/usr/bin/env bash
set -euo pipefail

# Utility script to back up or restore every "data" directory in the repo via cloud storage.
# Supports AWS S3 (default) and Tencent Cloud COS.
#
# Environment overrides:
#   - DEFAULT_S3_PREFIX: default S3 destination/search prefix
#   - DEFAULT_COS_PREFIX: default COS destination/search prefix
# If not provided, sensible built-in defaults are used below.
: "${DEFAULT_S3_PREFIX:=s3://your-bucket/your/prefix}"
: "${DEFAULT_COS_PREFIX:=cos://your-bucket/your/prefix}"

usage() {
  cat <<'USAGE'
Usage:
  data_backup_restore.sh backup [URI] [OPTIONS]
  data_backup_restore.sh restore [URI] [OPTIONS]
  data_backup_restore.sh test [OPTIONS]

Commands:
  backup    Create and upload a tarball of all data directories
  restore   Download and extract a tarball
  test      Run validation tests without cloud operations

Options:
  --provider PROVIDER    Cloud provider: aws (default) or cos
  --keep-local          Leave the generated tarball on disk after uploading (backup only)
  --target-dir PATH     Extract into a different directory (restore only)
  --dry-run            Show what would be done without executing
  -h, --help           Show this help message

Environment Variables:
  KEEP_LOCAL_TARBALL=true    Acts like --keep-local
  CLOUD_PROVIDER=cos         Sets default provider (aws or cos)
  DEFAULT_S3_PREFIX          Default S3 destination/search prefix
  DEFAULT_COS_PREFIX         Default COS destination/search prefix

URI Formats:
  AWS S3:         s3://bucket/prefix
  Tencent COS:    cos://bucket/prefix

Defaults:
  AWS:  ${DEFAULT_S3_PREFIX}
  COS:  ${DEFAULT_COS_PREFIX}

Provider Auto-detection:
  - s3:// URIs → aws provider
  - cos:// URIs → cos provider
  - No URI → uses --provider or CLOUD_PROVIDER (defaults to aws)

Examples:
  # Backup to AWS S3 (default)
  data_backup_restore.sh backup

  # Backup to Tencent COS
  data_backup_restore.sh backup --provider cos
  data_backup_restore.sh backup cos://my-bucket/path/

  # Restore from specific tarball
  data_backup_restore.sh restore s3://bucket/path/archive.tar.gz

  # Dry-run to test without cloud access
  data_backup_restore.sh backup --dry-run
  data_backup_restore.sh restore --dry-run --provider cos

  # Run validation tests
  data_backup_restore.sh test

Notes:
  - AWS requires 'aws' CLI installed and configured
  - COS requires 'cos' CLI installed and configured (from coscli package)
USAGE
}

require_aws() {
  if ! command -v aws >/dev/null 2>&1; then
    echo "aws CLI not found in PATH" >&2
    echo "Install: pip install awscli" >&2
    exit 1
  fi
}

require_cos() {
  if ! command -v cos >/dev/null 2>&1; then
    echo "cos CLI not found in PATH" >&2
    echo "Install: pip install tencent-cos-cli" >&2
    exit 1
  fi
}

detect_provider_from_uri() {
  local uri="$1"
  if [[ "$uri" =~ ^s3:// ]]; then
    echo "aws"
  elif [[ "$uri" =~ ^cos:// ]]; then
    echo "cos"
  else
    echo ""
  fi
}

get_default_prefix() {
  local provider="$1"
  case "$provider" in
    aws) echo "$DEFAULT_S3_PREFIX" ;;
    cos) echo "$DEFAULT_COS_PREFIX" ;;
    *) echo "" ;;
  esac
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# REPO_ROOT is one level up from setup/
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CURRENT_DIR="$(pwd)"

ACTION="${1:-}"
[[ -z "$ACTION" ]] && { usage >&2; exit 1; }
shift

parse_s3_url() {
  local uri="$1"
  uri="${uri#s3://}"
  uri="${uri#cos://}"
  typeset -g CLOUD_BUCKET="${uri%%/*}"
  if [[ "$uri" == "$CLOUD_BUCKET" ]]; then
    typeset -g CLOUD_KEY=""
  else
    typeset -g CLOUD_KEY="${uri#*/}"
  fi
}

# Upload file using appropriate provider
cloud_upload() {
  local provider="$1"
  local local_path="$2"
  local remote_uri="$3"
  local dry_run="${4:-false}"

  if [[ "$dry_run" == "true" ]]; then
    echo "[DRY-RUN] Would upload: $local_path → $remote_uri"
    return 0
  fi

  case "$provider" in
    aws)
      echo "Uploading to AWS S3: $remote_uri"
      aws s3 cp "$local_path" "$remote_uri"
      ;;
    cos)
      echo "Uploading to Tencent COS: $remote_uri"
      cos cp "$local_path" "$remote_uri"
      ;;
    *)
      echo "Unknown provider: $provider" >&2
      return 1
      ;;
  esac
}

# Download file using appropriate provider
cloud_download() {
  local provider="$1"
  local remote_uri="$2"
  local local_path="$3"
  local dry_run="${4:-false}"

  if [[ "$dry_run" == "true" ]]; then
    echo "[DRY-RUN] Would download: $remote_uri → $local_path"
    return 0
  fi

  case "$provider" in
    aws)
      echo "Downloading from AWS S3: $remote_uri"
      aws s3 cp "$remote_uri" "$local_path"
      ;;
    cos)
      echo "Downloading from Tencent COS: $remote_uri"
      cos cp "$remote_uri" "$local_path"
      ;;
    *)
      echo "Unknown provider: $provider" >&2
      return 1
      ;;
  esac
}

find_latest_tarball_uri() {
  local provider="$1"
  local search_prefix="$2"
  local dry_run="${3:-false}"

  if [[ "$dry_run" == "true" ]]; then
    echo "[DRY-RUN] Would search for latest tarball under: $search_prefix"
    echo "${search_prefix}/data_directories_20251221_120000.tar.gz"
    return 0
  fi

  parse_s3_url "$search_prefix"
  local key_prefix="$CLOUD_KEY"
  if [[ -n "$key_prefix" && "$key_prefix" != */ ]]; then
    key_prefix="$key_prefix/"
  fi

  case "$provider" in
    aws)
      local query='sort_by(Contents,&LastModified)[?ends_with(Key, `tar.gz`)] | [-1].Key'
      local latest_key
      latest_key="$(aws s3api list-objects-v2 --bucket "$CLOUD_BUCKET" --prefix "$key_prefix" --output text --query "$query")"
      if [[ -z "$latest_key" || "$latest_key" == "None" ]]; then
        echo "No tar.gz objects found under $search_prefix" >&2
        return 1
      fi
      echo "s3://$CLOUD_BUCKET/$latest_key"
      ;;
    cos)
      # List files and find latest .tar.gz
      local temp_list="$(mktemp)"
      cos ls "${search_prefix%/}/" --output text 2>/dev/null | grep '\.tar\.gz$' | sort > "$temp_list" || true
      local latest_file
      latest_file="$(tail -n 1 "$temp_list")"
      rm -f "$temp_list"
      
      if [[ -z "$latest_file" ]]; then
        echo "No tar.gz objects found under $search_prefix" >&2
        return 1
      fi
      
      # Extract just the filename
      latest_file="${latest_file##*/}"
      echo "${search_prefix%/}/${latest_file}"
      ;;
    *)
      echo "Unknown provider: $provider" >&2
      return 1
      ;;
  esac
}

case "$ACTION" in
  test)
    echo "=== Running Validation Tests ==="
    echo ""
    
    # Test 1: Check CLI availability
    echo "Test 1: CLI Availability"
    if command -v aws >/dev/null 2>&1; then
      echo "  ✓ AWS CLI found: $(aws --version 2>&1 | head -n1)"
    else
      echo "  ✗ AWS CLI not found"
    fi
    
    if command -v cos >/dev/null 2>&1; then
      echo "  ✓ COS CLI found: $(cos --version 2>&1 | head -n1)"
    else
      echo "  ✗ COS CLI not found"
    fi
    echo ""
    
    # Test 2: Provider detection
    echo "Test 2: Provider Detection"
    test_uris=("s3://bucket/path" "cos://bucket/path" "invalid://bucket")
    for uri in "${test_uris[@]}"; do
      detected="$(detect_provider_from_uri "$uri")"
      if [[ -n "$detected" ]]; then
        echo "  ✓ $uri → $detected"
      else
        echo "  ✗ $uri → (not detected)"
      fi
    done
    echo ""
    
    # Test 3: Dry-run backup
    echo "Test 3: Dry-run Backup (AWS)"
    "$0" backup --dry-run --provider aws 2>&1 | head -n 10
    echo ""
    
    # Test 4: Dry-run backup (COS)
    echo "Test 4: Dry-run Backup (COS)"
    "$0" backup --dry-run --provider cos 2>&1 | head -n 10
    echo ""
    
    # Test 5: Dry-run restore
    echo "Test 5: Dry-run Restore"
    "$0" restore --dry-run --provider cos 2>&1 | head -n 10
    echo ""
    
    echo "=== Tests Complete ==="
    ;;

  backup)
    PROVIDER="${CLOUD_PROVIDER:-aws}"
    CLOUD_PREFIX=""
    KEEP_LOCAL="${KEEP_LOCAL_TARBALL:-false}"
    DRY_RUN="false"

    while [[ $# -gt 0 ]]; do
      case "$1" in
        --provider)
          PROVIDER="${2:-}"
          if [[ "$PROVIDER" != "aws" && "$PROVIDER" != "cos" ]]; then
            echo "Invalid provider: $PROVIDER (must be aws or cos)" >&2
            exit 1
          fi
          shift 2
          ;;
        --keep-local)
          KEEP_LOCAL="true"
          shift
          ;;
        --dry-run)
          DRY_RUN="true"
          shift
          ;;
        s3://*|cos://*)
          CLOUD_PREFIX="$1"
          # Auto-detect provider from URI
          detected="$(detect_provider_from_uri "$CLOUD_PREFIX")"
          if [[ -n "$detected" ]]; then
            PROVIDER="$detected"
          fi
          shift
          ;;
        -h|--help)
          usage
          exit 0
          ;;
        *)
          echo "Unrecognized argument: $1" >&2
          usage >&2
          exit 1
          ;;
      esac
    done

    # Set default prefix if not provided
    if [[ -z "$CLOUD_PREFIX" ]]; then
      CLOUD_PREFIX="$(get_default_prefix "$PROVIDER")"
      if [[ -z "$CLOUD_PREFIX" ]]; then
        echo "No default prefix for provider: $PROVIDER" >&2
        exit 1
      fi
    fi

    # Check CLI availability
    if [[ "$DRY_RUN" != "true" ]]; then
      case "$PROVIDER" in
        aws) require_aws ;;
        cos) require_cos ;;
      esac
    fi

    data_dirs=()
    while IFS= read -r dir; do
      dir="${dir#./}"
      data_dirs+=("$dir")
    done < <(cd "$CURRENT_DIR" && find . -type d -name data -print | sort)

    if (( ${#data_dirs[@]} == 0 )); then
      echo "No data directories found under $CURRENT_DIR" >&2
      exit 1
    fi

    TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
    TARBALL_NAME="data_directories_${TIMESTAMP}.tar.gz"
    TARBALL_PATH="$CURRENT_DIR/$TARBALL_NAME"

    echo "Provider: $PROVIDER"
    echo "Destination: $CLOUD_PREFIX"
    echo "Creating tarball $TARBALL_NAME including:"
    printf '  %s\n' "${data_dirs[@]}"

    if [[ "$DRY_RUN" == "true" ]]; then
      echo "[DRY-RUN] Would create: $TARBALL_PATH"
      echo "[DRY-RUN] Would include ${#data_dirs[@]} directories"
    else
      tar -czf "$TARBALL_PATH" -C "$CURRENT_DIR" "${data_dirs[@]}"
      echo "Tarball created at $TARBALL_PATH"
    fi

    cloud_upload "$PROVIDER" "$TARBALL_PATH" "$CLOUD_PREFIX/$TARBALL_NAME" "$DRY_RUN"

    if [[ "$DRY_RUN" != "true" && "$KEEP_LOCAL" != "true" ]]; then
      rm -f "$TARBALL_PATH"
      echo "Local tarball removed; use --keep-local to retain it."
    elif [[ "$KEEP_LOCAL" == "true" ]]; then
      echo "Local tarball kept at: $TARBALL_PATH"
    fi
    ;;

  restore)
    PROVIDER="${CLOUD_PROVIDER:-aws}"
    TARBALL_URI=""
    CLOUD_SEARCH_PREFIX=""
    TARGET_DIR="$CURRENT_DIR"
    DRY_RUN="false"

    while [[ $# -gt 0 ]]; do
      case "$1" in
        --provider)
          PROVIDER="${2:-}"
          if [[ "$PROVIDER" != "aws" && "$PROVIDER" != "cos" ]]; then
            echo "Invalid provider: $PROVIDER (must be aws or cos)" >&2
            exit 1
          fi
          shift 2
          ;;
        --target-dir)
          TARGET_DIR="${2:-}"
          if [[ -z "$TARGET_DIR" ]]; then
            echo "--target-dir expects a value" >&2
            exit 1
          fi
          shift 2
          ;;
        --dry-run)
          DRY_RUN="true"
          shift
          ;;
        s3://*|cos://*)
          # Auto-detect provider from URI
          detected="$(detect_provider_from_uri "$1")"
          if [[ -n "$detected" ]]; then
            PROVIDER="$detected"
          fi
          
          if [[ "$1" == *.tar.gz ]]; then
            TARBALL_URI="$1"
          else
            CLOUD_SEARCH_PREFIX="$1"
          fi
          shift
          ;;
        -h|--help)
          usage
          exit 0
          ;;
        *)
          echo "Unrecognized argument: $1" >&2
          usage >&2
          exit 1
          ;;
      esac
    done

    # Check CLI availability
    if [[ "$DRY_RUN" != "true" ]]; then
      case "$PROVIDER" in
        aws) require_aws ;;
        cos) require_cos ;;
      esac
    fi

    if [[ -z "$TARBALL_URI" ]]; then
      CLOUD_SEARCH_PREFIX="${CLOUD_SEARCH_PREFIX:-$(get_default_prefix "$PROVIDER")}"
      echo "Provider: $PROVIDER"
      echo "Locating latest tarball under $CLOUD_SEARCH_PREFIX"
      if ! TARBALL_URI="$(find_latest_tarball_uri "$PROVIDER" "$CLOUD_SEARCH_PREFIX" "$DRY_RUN")"; then
        exit 1
      fi
      echo "Using $TARBALL_URI"
    else
      echo "Provider: $PROVIDER"
      echo "Using specified tarball: $TARBALL_URI"
    fi

    if [[ "$DRY_RUN" != "true" && ! -d "$TARGET_DIR" ]]; then
      echo "Target directory '$TARGET_DIR' does not exist" >&2
      exit 1
    fi

    if [[ "$DRY_RUN" != "true" ]]; then
      TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
    fi

    TMP_DIR="$(mktemp -d)"
    TARBALL_NAME="${TARBALL_URI##*/}"
    LOCAL_TARBALL="$TMP_DIR/$TARBALL_NAME"

    cleanup() {
      rm -rf "$TMP_DIR"
    }
    trap cleanup EXIT

    cloud_download "$PROVIDER" "$TARBALL_URI" "$LOCAL_TARBALL" "$DRY_RUN"

    if [[ "$DRY_RUN" == "true" ]]; then
      echo "[DRY-RUN] Would extract to: $TARGET_DIR"
    else
      echo "Extracting into $TARGET_DIR"
      tar -xzf "$LOCAL_TARBALL" -C "$TARGET_DIR"
      echo "Restore complete."
    fi
    ;;

  -h|--help)
    usage
    ;;

  *)
    echo "Unknown action: $ACTION" >&2
    usage >&2
    exit 1
    ;;
esac
