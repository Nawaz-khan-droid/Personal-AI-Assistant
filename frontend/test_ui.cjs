const puppeteer = require('puppeteer');

(async () => {
    console.log("Launching Puppeteer...");
    const browser = await puppeteer.launch({
        headless: true,
        args: [
            '--use-fake-ui-for-media-stream',
            '--use-fake-device-for-media-stream'
        ]
    });
    
    const page = await browser.newPage();
    
    // Capture console logs from the page
    page.on('console', msg => {
        if (msg.type() === 'error') {
            console.log('BROWSER ERROR:', msg.text());
        } else {
            console.log('BROWSER LOG:', msg.text());
        }
    });

    page.on('pageerror', err => {
        console.log('PAGE EXCEPTION:', err.message);
    });

    console.log("Navigating to http://localhost:8000 ...");
    await page.goto('http://localhost:8000');
    
    console.log("Waiting for password input...");
    await page.waitForSelector('input[type="password"]');
    await page.type('input[type="password"]', 'jarvis_secure_123'); // Assuming default password or we can bypass
    
    console.log("Clicking Connect...");
    await page.click('button[type="submit"]'); // Adjust selector if needed
    
    console.log("Waiting 15 seconds for connection and transcript generation...");
    await new Promise(r => setTimeout(r, 15000));
    
    console.log("Closing browser...");
    await browser.close();
})();
