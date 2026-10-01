@echo off
echo ================================================================================
echo   kake_product_data_scientist_bridge_project (GP-123)
echo   Automated Execution, Testing and Quantitative Benchmarks
echo ================================================================================
echo.

echo [1/4] Generating Calibrated Stochastic Domain Dataset...
python src/data_generator.py --records 50000
if %ERRORLEVEL% NEQ 0 (echo [ERROR] Data generator failed && exit /b %ERRORLEVEL%)

echo.
echo [2/4] Executing Executive Rich TUI & Analytics Engine...
python src/interface.py
if %ERRORLEVEL% NEQ 0 (echo [ERROR] Executive interface failed && exit /b %ERRORLEVEL%)

echo.
echo [3/4] Running Automated Pytest Suite...
python -m pytest tests/ -v
if %ERRORLEVEL% NEQ 0 (echo [ERROR] Pytest suite failed && exit /b %ERRORLEVEL%)

echo.
echo [4/4] Running Quantitative Latency Benchmarks (30 iterations)...
python tests/benchmark.py
if %ERRORLEVEL% NEQ 0 (echo [ERROR] Benchmark failed && exit /b %ERRORLEVEL%)

echo.
echo ================================================================================
echo   Execution Complete: All Tests and Latency Targets Passed!
echo ================================================================================