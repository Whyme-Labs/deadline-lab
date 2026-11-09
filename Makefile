.PHONY: build test verify doctor qnx
build:
	cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
	cmake --build build -j2
test: build
	ctest --test-dir build --output-on-failure
	python3 -S -m unittest discover -s tests -p 'test_*.py' -v
verify:
	./scripts/verify-local.sh
doctor:
	python3 -S -m deadline_lab doctor
qnx:
	./scripts/build-qnx.sh
