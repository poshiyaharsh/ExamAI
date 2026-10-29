import { chromium } from 'playwright';
import { spawn } from 'child_process';
import http from 'http';

const PORT = 3188;
const BASE_URL = `http://127.0.0.1:${PORT}`;

const studentSession = {
  access: "mockStudentToken",
  refresh: "mockStudentRefresh",
  role: "student",
  user: {
    id: 10,
    first_name: "Grace",
    last_name: "Hopper",
    email: "student@test.edu",
    institution: { id: 1, name: "Test University" }
  }
};

const facultySession = {
  access: "mockFacultyToken",
  refresh: "mockFacultyRefresh",
  role: "faculty",
  user: {
    id: 20,
    first_name: "Alan",
    last_name: "Turing",
    email: "faculty@test.edu",
    institution: { id: 1, name: "Test University" }
  }
};

function waitForServer(url, timeoutMs = 15000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      http.get(url, (res) => {
        resolve(true);
      }).on('error', () => {
        if (Date.now() - start > timeoutMs) {
          reject(new Error(`Server at ${url} did not start within ${timeoutMs}ms`));
        } else {
          setTimeout(check, 250);
        }
      });
    };
    check();
  });
}

async function run() {
  console.log('--- Starting One-Warning Auto-Submit Playwright Verification ---');

  console.log(`Starting Vite preview on port ${PORT}...`);
  const previewProcess = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--port', String(PORT), '--host', '127.0.0.1'], {
    cwd: 'Front-End',
    stdio: 'ignore'
  });

  try {
    await waitForServer(BASE_URL);
    console.log(`Preview server ready at ${BASE_URL}`);

    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await context.newPage();

    let violationCount = 0;
    let attemptFinalized = false;

    // Log console from browser
    page.on('console', msg => console.log('BROWSER LOG:', msg.text()));

    // Mock API requests using regex matching any domain / port
    await page.route(/.*\/api\/.*/, async (route) => {
      const url = route.request().url();
      console.log(`[ROUTE MATCH] ${route.request().method()} ${url}`);

      // Exam start / resume
      if (url.includes('/api/student/exams/1/start/')) {
        const now = new Date();
        const deadline = new Date(now.getTime() + 60 * 60 * 1000);
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            attempt_id: 1,
            max_warnings: 1,
            created: true,
            started_at: now.toISOString(),
            deadline: deadline.toISOString(),
            expires_at: deadline.toISOString(),
            duration_seconds: 3600,
            session_token: "mockSessionToken123",
            violation_count: 0,
            exam: {
              id: 1,
              title: "Systems Security Exam",
              duration_minutes: 60,
              total_marks: 20,
              max_warnings: 1,
              allow_retakes: false,
              questions: [
                {
                  id: 101,
                  order: 1,
                  text: "What is an atomic transaction?",
                  question_type: "mcq",
                  options: ["All-or-nothing execution", "A partial operation", "A network ping", "None"],
                  marks: 10
                }
              ]
            }
          })
        });
      }

      // Violation endpoint
      if (url.includes('/api/student/attempts/1/violation/')) {
        violationCount += 1;
        console.log(`[API Mock] Handling violation call #${violationCount}`);
        if (violationCount === 1) {
          return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              auto_submitted: false,
              violation_count: 1,
              max_warnings: 1,
              warnings_left: 0,
              message: "Final warning: you left the exam screen. Another violation will submit your exam automatically."
            })
          });
        } else {
          attemptFinalized = true;
          return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              auto_submitted: true,
              status: "auto_submitted",
              submit_reason: "violations",
              violation_count: 2,
              max_warnings: 1,
              warnings_left: 0,
              redirect_url: "/student/results/1",
              message: "Violation limit exceeded (2/1). The exam has been automatically submitted."
            })
          });
        }
      }

      // Heartbeat
      if (url.includes('/api/student/attempts/1/heartbeat/')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            active: !attemptFinalized,
            auto_submitted: attemptFinalized,
            already_submitted: attemptFinalized,
            submit_reason: attemptFinalized ? "violations" : null,
            redirect_url: attemptFinalized ? "/student/results/1" : null,
            server_now: new Date().toISOString(),
            seconds_left: 3500
          })
        });
      }

      // Save answer
      if (url.includes('/api/student/attempts/1/save/')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ saved: true })
        });
      }

      // Faculty attempt review endpoint
      if (url.includes('/api/faculty/attempts/1/')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            attempt_id: 1,
            exam_id: 1,
            exam_title: "Systems Security Exam",
            status: "auto_submitted",
            submit_reason: "violations",
            total_score: 10,
            max_score: 20,
            answers: []
          })
        });
      }

      // Default fallback for any other api call
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'ok' })
      });
    });

    // Authenticate as Student
    await page.addInitScript(({ session }) => {
      window.sessionStorage.setItem("exam_ai_auth", JSON.stringify(session));
      window.localStorage.setItem("exam_ai_auth", JSON.stringify(session));
    }, { session: studentSession });

    console.log('Navigating to take exam page...');
    await page.goto(`${BASE_URL}/student/exams/1/take`, { waitUntil: "domcontentloaded" });

    // 1. Verify Pre-Exam Rules Modal Text
    console.log('1. Checking Pre-Exam Instructions modal...');
    await page.waitForSelector('text=Assessment Integrity Rules');
    const instructionText = await page.textContent('body');
    if (!instructionText.includes('1 warning, then automatic submission')) {
      throw new Error(`Expected instructions to contain "1 warning, then automatic submission", got: ${instructionText.slice(0, 300)}`);
    }
    console.log('✓ Verified: Pre-exam rules explicitly show "1 warning, then automatic submission".');

    // 2. Accept rules and start exam
    console.log('2. Starting exam...');
    await page.click('input[type="checkbox"]');
    await page.click('button:has-text("Enter Fullscreen & Start Exam")');

    // 3. Check warning counter badge
    console.log('3. Checking Warning Counter badge...');
    await page.waitForSelector('text=Warnings 0/1');
    console.log('✓ Verified: Warning counter displays "Warnings 0/1".');

    // Wait past debounce window
    await page.waitForTimeout(1200);

    // 4. Trigger Violation 1: Exit fullscreen
    console.log('4. Simulating Violation 1 (Fullscreen exit)...');
    await page.evaluate(() => {
      document.dispatchEvent(new Event('fullscreenchange'));
    });

    // 5. Verify Warning Modal appears with exact text and button
    console.log('5. Verifying Warning Modal...');
    await page.waitForSelector('text=Final warning: you left the exam screen. Another violation will submit your exam automatically.');
    await page.waitForSelector('button:has-text("Return to fullscreen")');
    console.log('✓ Verified: Blocking modal displayed with "Final warning: you left the exam screen. Another violation will submit your exam automatically." and "Return to fullscreen" button.');

    // 6. Return to fullscreen
    console.log('6. Clicking "Return to fullscreen"...');
    await page.click('button:has-text("Return to fullscreen")');
    await page.waitForTimeout(500);

    // 7. Trigger Violation 2: Exit fullscreen again -> AUTO-SUBMITS
    console.log('7. Simulating Violation 2 (Second exit)...');
    // Ensure debounce window has passed
    await page.waitForTimeout(1200);
    await page.evaluate(() => {
      document.dispatchEvent(new Event('fullscreenchange'));
    });

    // 8. Verify auto-submit toast and navigation
    console.log('8. Verifying auto-submit reaction...');
    await page.waitForSelector('text=Your exam was submitted automatically because of repeated rule violations.');
    console.log('✓ Verified: Toast displays "Your exam was submitted automatically because of repeated rule violations."');

    // Wait for redirect to results
    await page.waitForURL('**/student/results/1');
    console.log('✓ Verified: Redirected to results screen /student/results/1.');

    // 9. Faculty can open submitted attempt
    console.log('9. Checking faculty view of auto-submitted attempt...');
    const ctxFaculty = await browser.newContext();
    const pageFaculty = await ctxFaculty.newPage();
    await pageFaculty.addInitScript(({ session }) => {
      window.sessionStorage.setItem("exam_ai_auth", JSON.stringify(session));
      window.localStorage.setItem("exam_ai_auth", JSON.stringify(session));
    }, { session: facultySession });

    const facultyResp = await pageFaculty.request.get(`http://127.0.0.1:8000/api/faculty/attempts/1/`);
    const facultyData = await facultyResp.json();
    if (facultyData.status !== 'auto_submitted' || facultyData.submit_reason !== 'violations') {
      throw new Error(`Expected faculty view to show status=auto_submitted and submit_reason=violations, got: ${JSON.stringify(facultyData)}`);
    }
    console.log('✓ Verified: Faculty successfully fetched submitted attempt with status="auto_submitted" and submit_reason="violations".');

    await browser.close();
    console.log('\nALL PLAYWRIGHT TESTS PASSED SUCCESSFULLY! ✓✓✓');
    process.exit(0);
  } catch (err) {
    console.error('Playwright Test Failed:', err);
    process.exit(1);
  } finally {
    previewProcess.kill();
  }
}

run();
