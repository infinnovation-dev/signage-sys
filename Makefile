signage.built:	signage/Dockerfile
	docker build -t signage-sys signage
	touch $@

signage/Dockerfile:	signage.py signage.yaml
	PYTHONPATH=iisysgen python3 -m iisysgen build -c signage.yaml signage

signage.exported:	signage.built export-filetree fixup-docker
	mkdir -p signage.fs
	docker run \
	   --mount=type=bind,source="`pwd`",destination=/helpers \
	   --mount=type=bind,source="`pwd`/signage.fs",destination=/target \
	    signage-sys \
	    /helpers/export-filetree
	touch $@

.PRECIOUS:	%/Dockerfile
