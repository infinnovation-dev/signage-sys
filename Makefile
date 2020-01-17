#=======================================================================
#	Set PIWALLINST to e.g. piwall-dev/stretch-install
#=======================================================================

IISYSGEN = PYTHONPATH=iisysgen python3 -m iisysgen.cmd

PIWALL_BINS = pwimg pwcaption pwticker pwsnap
PIWALL_LIBS = libpwdisp libpwmover libpwmsrv libpwtilemap libpwutil
PIWALL_PY = defs __init__

PWSRCBIN = $(addprefix $(PIWALLINST)/bin/,$(PIWALL_BINS))
PWSRCLIB = $(foreach lib,$(PIWALL_LIBS),$(wildcard $(PIWALLINST)/lib/$(lib).so*))
PWSRCPY = $(foreach py,$(PIWALL_PY),$(PIWALLINST)/lib/python2.7/dist-packages/piwall/$(py).py)

signage.img:	signage.exported usrlocal.built ccfe-signage.exported
	sudo ./signage-mkimg

ccfe-signage.exported:	FORCE
	$(MAKE) -C ccfe-signage export

usrlocal.built:	ccfe-authen/ccfe-authen.tgz piwall-subset.tgz
	rm -fr usrlocal
	mkdir usrlocal
	tar xz -C usrlocal -f ccfe-authen/ccfe-authen.tgz
	tar xz -C usrlocal -f piwall-subset.tgz
	touch $@

piwall-subset.tgz:	piwall-subset
	tar cz -f $@ -C piwall-subset .

ifeq ($(PIWALLINST),)
piwall-subset:
	@echo You need to define PIWALLINST
	@exit 1
else
piwall-subset:	FORCE
	mkdir -p $@
	rsync -av $(PWSRCBIN) $@/bin/
	rsync -av $(PWSRCLIB) $@/lib/
	mkdir -p $@/lib/python3.5/dist-packages/piwall/
	rsync -av $(PWSRCPY) $@/lib/python3.5/dist-packages/piwall/
endif

# piwall-subset.tgz to be imported manually
ccfe-authen/ccfe-authen.tgz:	FORCE
	$(MAKE) -C ccfe-authen ccfe-authen.tgz

signage.built:	signage/Dockerfile
	docker build -t signage-sys signage
	touch $@

signage/Dockerfile:	signage.py signage.yaml
	$(IISYSGEN) generate -c signage.yaml signage

signage.exported:	signage.built export-filetree fixup-docker
	mkdir -p signage.fs
	docker run \
	   --mount=type=bind,source="`pwd`",destination=/helpers \
	   --mount=type=bind,source="`pwd`/signage.fs",destination=/target \
	    signage-sys \
	    /helpers/export-filetree
	touch $@

.PRECIOUS:	%/Dockerfile
.PHONY:	FORCE %.built %.exported
