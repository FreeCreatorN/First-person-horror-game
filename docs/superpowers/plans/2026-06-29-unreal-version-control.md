# Unreal Engine Version Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Initialize `D:\UE\Project\HorrorGame` as a local Git repository whose Unreal Engine binary assets are stored through Git LFS and whose generated files are excluded.

**Architecture:** Keep source project inputs (`HorrorGame.uproject`, `Config/`, `Content/`, and any future `Source/` or `Plugins/`) in Git. Exclude regenerable Unreal/IDE output with `.gitignore`, route binary source assets through Git LFS with `.gitattributes`, and create one local baseline commit.

**Tech Stack:** Git for Windows 2.45.1, Git LFS 3.5.1, Unreal Engine 5 project files.

## Global Constraints

- Run all repository commands from `D:\UE\Project\HorrorGame`, which contains `HorrorGame.uproject`.
- Do not delete, move, or rewrite existing Unreal project assets.
- Do not add `Binaries/`, `DerivedDataCache/`, `Intermediate/`, or `Saved/` to Git.
- Track `.uasset`, `.umap`, 3D source files, source images, audio, and video with Git LFS.
- Keep the repository local; do not create or publish a remote repository.

---

### Task 1: Initialize Git and add Unreal Engine repository rules

**Files:**
- Create: `.git/`
- Create: `.gitignore`
- Create: `.gitattributes`

**Interfaces:**
- Consumes: The Unreal Engine project directory layout and installed Git tooling.
- Produces: Git ignore decisions and Git LFS attribute decisions used by the initial index.

- [ ] **Step 1: Initialize Git locally**

Run:

```powershell
git init -b main
git lfs install --local
```

Expected: Git creates `.git/`; Git LFS reports that hooks were updated and LFS was initialized.

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Unreal Engine generated folders
Binaries/
DerivedDataCache/
Intermediate/
Saved/
**/Binaries/
**/Intermediate/

# Visual Studio
.vs/
*.sln
*.suo
*.opensdf
*.sdf
*.VC.db
*.VC.opendb

# Rider / JetBrains
.idea/

# Xcode
*.xcodeproj
*.xcworkspace

# Operating system
.DS_Store
Thumbs.db

# Temporary files
*.tmp
*.temp
*.log
```

- [ ] **Step 3: Create `.gitattributes`**

```gitattributes
# Unreal Engine binary assets
*.uasset filter=lfs diff=lfs merge=lfs -text
*.umap filter=lfs diff=lfs merge=lfs -text

# 3D source files
*.fbx filter=lfs diff=lfs merge=lfs -text
*.obj filter=lfs diff=lfs merge=lfs -text
*.blend filter=lfs diff=lfs merge=lfs -text

# Images
*.png filter=lfs diff=lfs merge=lfs -text
*.jpg filter=lfs diff=lfs merge=lfs -text
*.jpeg filter=lfs diff=lfs merge=lfs -text
*.tga filter=lfs diff=lfs merge=lfs -text
*.exr filter=lfs diff=lfs merge=lfs -text
*.psd filter=lfs diff=lfs merge=lfs -text

# Audio and video
*.wav filter=lfs diff=lfs merge=lfs -text
*.mp3 filter=lfs diff=lfs merge=lfs -text
*.ogg filter=lfs diff=lfs merge=lfs -text
*.mp4 filter=lfs diff=lfs merge=lfs -text
*.mov filter=lfs diff=lfs merge=lfs -text
```

- [ ] **Step 4: Verify representative ignore and attribute rules**

Run:

```powershell
git check-ignore -v --no-index Intermediate Saved DerivedDataCache
git check-attr filter diff merge text -- Content/**/*.uasset Content/**/*.umap
```

Expected: generated directories match `.gitignore`; Unreal asset paths report `filter=lfs`, `diff=lfs`, `merge=lfs`, and `text=unset`.

### Task 2: Initialize and capture the baseline

**Files:**
- Modify: Git index and local repository history

**Interfaces:**
- Consumes: `.gitignore`, `.gitattributes`, and current project files.
- Produces: A `main` branch with one local initial commit.

- [ ] **Step 1: Add the project baseline**

Run:

```powershell
git add .
```

Expected: project inputs are staged, generated directories are absent, and LFS-managed files are represented by LFS pointers in Git's staged content.

- [ ] **Step 2: Audit the staged baseline**

Run:

```powershell
git status --short
git lfs ls-files
git diff --cached --name-only
```

Expected: `HorrorGame.uproject`, `Config/`, `Content/`, repository rules, and this plan are staged; no path begins with `Binaries/`, `DerivedDataCache/`, `Intermediate/`, or `Saved/`.

- [ ] **Step 3: Create the initial local version**

Run:

```powershell
git commit -m "chore: initialize Unreal Engine version control"
```

Expected: Git creates the root commit on `main`.

- [ ] **Step 4: Verify the final repository**

Run:

```powershell
git status --short --branch
git log -1 --oneline
git lfs ls-files
```

Expected: branch is `main`, the working tree is clean, the root commit is present, and Unreal binary assets are listed by Git LFS.
