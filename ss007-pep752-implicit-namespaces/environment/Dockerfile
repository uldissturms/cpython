FROM ubuntu@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852

ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -yq --no-install-recommends \
    build-essential=12.10ubuntu1 \
    pkg-config=1.8.1-2build1 \
    ca-certificates=20260816ubuntu0.24.04.1 \
    git=1:2.43.0-1ubuntu7.4 \
    python3=3.12.3-0ubuntu2.1 \
    libssl-dev=3.0.13-0ubuntu3.16 \
    zlib1g-dev=1:1.3.dfsg-3.1ubuntu2.3 \
    libncurses-dev=6.4+20240113-1ubuntu2.2 \
    libbz2-dev=1.0.8-5.1ubuntu0.1 \
    libreadline-dev=8.2-4build1 \
    libsqlite3-dev=3.45.1-1ubuntu2.9 \
    libffi-dev=3.4.6-1build1 \
    liblzma-dev=5.6.1+really5.4.5-1ubuntu0.4 \
    libgdbm-dev=1.23-5.1build1 \
    libgdbm-compat-dev=1.23-5.1build1 \
    uuid-dev=2.39.3-9ubuntu6.6 \
    libexpat1-dev=2.6.1-2ubuntu0.6 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# One commit, fetched shallow: the tree test.sh and solve.sh patch.
RUN git init -q /app && cd /app \
 && git remote add origin https://github.com/python/cpython.git \
 && git fetch -q --depth 1 origin 416e8d89f57ac39f0ca8187dc6bc44f5f6ff994c \
 && git checkout -q 416e8d89f57ac39f0ca8187dc6bc44f5f6ff994c \
 && git clean -fdq

# Stage shared extensions as COPIES, not symlinks. CPython's `sharedmods`
# rule is PHONY, so every agent `make` recreates 75 build/*.so links, and
# a link-bearing tree refuses artifact capture (measured: the pre-push
# trial's agent ran make twice and broke the separate verifier). Patching
# Makefile.pre.in (not the generated Makefile) survives the config.status
# regeneration the agent's own Makefile.pre.in edit triggers. The `-sf `
# match hits only this rule: the install rules use `$(LN) -s` without -f.
RUN cd /app \
 && sed -i 's|$(LN) -sf ../../$$mod $$target/`basename $$mod`|cp -f $$mod $$target/`basename $$mod`|' Makefile.pre.in \
 && sed -i 's|# create relative links from build/lib\.platform/egg\.so to Modules/egg\.so|# copy build/lib.platform/egg.so from Modules/egg.so (copies, never links: link-bearing trees refuse artifact capture)|' Makefile.pre.in \
 && grep -q 'cp -f \$\$mod' Makefile.pre.in \
 && ! grep -q 'LN) -sf ../../' Makefile.pre.in

# Capped to the task's declared shape (task.toml [environment] cpus = 4):
# an unbounded make reads the host's core count and OOMs under Nest's cap.
# No `|| true`: a failed make must fail the build loudly (a swallowed
# sharedmods failure once shipped an image with no staged extensions).
# The .so count asserts sharedmods actually staged (currently 75+).
RUN ./configure -q --prefix=/opt/python-ss007 --with-ensurepip=no \
 && make -j4 -s \
 && rm -rf build/__pycache__ 2>/dev/null \
 && test "$(find build/lib.* -name '*.so' | wc -l)" -gt 50

# Delink: replace every symlink under /app with a copy of its target.
# Separate-verifier artifact staging refuses trees holding CPython's links
# (Misc/mypy/* -> ../../Lib/*, build/*.so, libpython version links) and the
# capture fails; copies stage cleanly. Misc/ must stay in the tree (a docs
# test reads Misc/NEWS.d), so exclusion is not an option -- copy, don't cut.
# NOTE: RUN uses /bin/sh (dash) -- no `read -d` here; find -exec is POSIX.
RUN cd /app && find . -type l -exec sh -c 'for link do if [ -f "$link" ]; then cp -f -L "$link" "$link.__delink_tmp" && mv -f "$link.__delink_tmp" "$link"; elif [ -d "$link" ]; then target="$(readlink -f "$link")" && rm "$link" && cp -a "$target" "$link"; else echo "delink: leaving dangling link $link" >&2; fi; done' _ {} + && left=$(find . -type l | wc -l) && echo "delink: remaining symlinks: $left" && test "$left" -eq 0

# Freeze the image's mechanical tree changes (sharedmods copies above, the
# delink) as one commit: the agent's `git status` starts clean, so a tidy
# `git checkout -- .` cannot silently restore the link-creating rule or the
# checked-in links. Tracked-only: build products stay untracked.
RUN cd /app && git add -u \
 && (git diff --cached --quiet || git -c user.name="lambo-task" -c user.email="lambo-task@localhost" commit -qm "task image: frozen build inputs (sharedmods copies, delinked tree)") \
 && test -z "$(git status --porcelain --untracked-files=no)" \
 && git log --oneline -1

RUN mkdir -p /logs/verifier /tests
