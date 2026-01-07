Phase-2 Improvements Installed:

- utils/error_capture.py : capture_artifacts(driver, out_dir, prefix) for screenshot/HTML/console logs on failure
- utils/cdp.py           : wait_network_idle(driver, idle_ms=500, timeout=30) using performance logs
- utils/metrics.py       : kelly_from_trades(), sharpe_sortino() for normalized analytics

Wire-ups you should add:
1) Enable performance logs in make_chrome_driver():
   from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
   caps = DesiredCapabilities.CHROME
   caps["goog:loggingPrefs"] = {"browser": "ALL", "performance": "ALL"}
   driver = webdriver.Chrome(desired_capabilities=caps, options=opts)

2) Call wait_network_idle() before parsing results for stronger stability.

3) On any exception inside worker.run_single(...), call:
   capture_artifacts(self.driver, os.path.join(self.cfg.output_dir, "artifacts"), prefix="failure")

4) Use utils.metrics in trade_analysis_plugin.py to compute Kelly and risk-adjusted stats on normalized returns.
