import { chromium } from 'playwright';

const adminSession = {
  access: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzkyMzQ3NzE2LCJpYXQiOjE3OTIzNDU5MTYsImp0aSI6IjM5MjIwZWY3N2NmMDQ3NWE4Zjc2ZmY4Y2RlNzY3ZjE5IiwidXNlcl9pZCI6IjUiLCJyb2xlIjoiYWRtaW4iLCJpbnN0aXR1dGlvbl9pZCI6Mn0.affM7iXWe52pl8qhkn1Hz_aCkEplIvGkp8OqOSmN5rQ",
  refresh: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc5Mjk1MDcxNiwiaWF0IjoxNzkyMzQ1OTE2LCJqdGkiOiIyNmYwZGMyNmU4ZTM0ZWE3ODViNDQxOTg2NjFkOGE5NCIsInVzZXJfaWQiOiI1Iiwicm9sZSI6ImFkbWluIiwiaW5zdGl0dXRpb25faWQiOjJ9._ODALrJ10fBAZgAMYdFcvA7U24V1VMjW7-xAtlH2uPU",
  role: "admin",
  user: { id: 5, first_name: "HARSH", last_name: "POSHIYA", email: "poshiya.2102@gmail.com", institution: { id: 2, name: "GLS University" } }
};

const facultySession = {
  access: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzkyMzQ3NzIzLCJpYXQiOjE3OTIzNDU5MjMsImp0aSI6IjE5MmIzNzhjZjQ1ZjRjZDJiYzc1ZjEzOTgyMWZmNWM4IiwidXNlcl9pZCI6IjQiLCJyb2xlIjoiZmFjdWx0eSIsImluc3RpdHV0aW9uX2lkIjoyfQ.mGkZgO_aFZdHwE0YkhjBrck5qbmHa7eCrP4Y_W-9Pco",
  refresh: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc5Mjk1MDcyMywiaWF0IjoxNzkyMzQ1OTIzLCJqdGkiOiIyMzJjNmUyN2I0OWI0MjI0YTYxN2MwZDk4YTE0Y2E3OCIsInVzZXJfaWQiOiI0Iiwicm9sZSI6ImZhY3VsdHkiLCJpbnN0aXR1dGlvbl9pZCI6Mn0.aiOPB6e3vV7STlWCqvXzUVDlVXl29G-NenEMBTTnNL8",
  role: "faculty",
  user: { id: 4, first_name: "HARSH", last_name: "POSHIYA", email: "harsh.poshiya21@gmail.com", institution: { id: 2, name: "GLS University" } }
};

const viewports = [320, 375, 768, 1024, 1280, 1440, 1920];

async function run() {
  const browser = await chromium.launch({ headless: true });
  let failures = 0;

  try {
    for (const w of viewports) {
      for (const sidebarOpen of [true, false]) {
        // Admin Exams
        const ctxAdmin = await browser.newContext({ viewport: { width: w, height: 900 } });
        const pAdmin = await ctxAdmin.newPage();
        await pAdmin.addInitScript(({ session, sbOpen }) => {
          window.sessionStorage.setItem("exam_ai_auth", JSON.stringify(session));
          window.localStorage.setItem("examai-admin-sidebar-open", sbOpen ? "true" : "false");
        }, { session: adminSession, sbOpen: sidebarOpen });
        await pAdmin.goto("http://127.0.0.1:3000/admin/exams", { waitUntil: "networkidle" });
        await pAdmin.waitForTimeout(400);

        const checkAdmin = await pAdmin.evaluate(() => {
          const docEl = document.documentElement;
          const body = document.body;
          return docEl.scrollWidth <= docEl.clientWidth && body.scrollWidth <= body.clientWidth;
        });
        if (!checkAdmin) failures++;
        await ctxAdmin.close();

        // Faculty Dashboard
        const ctxFac = await browser.newContext({ viewport: { width: w, height: 900 } });
        const pFac = await ctxFac.newPage();
        await pFac.addInitScript(({ session, sbOpen }) => {
          window.sessionStorage.setItem("exam_ai_auth", JSON.stringify(session));
          window.localStorage.setItem("examai-faculty-sidebar-open", sbOpen ? "true" : "false");
        }, { session: facultySession, sbOpen: sidebarOpen });
        await pFac.goto("http://127.0.0.1:3000/faculty", { waitUntil: "networkidle" });
        await pFac.waitForTimeout(400);

        const checkFac = await pFac.evaluate(() => {
          const docEl = document.documentElement;
          const body = document.body;
          return docEl.scrollWidth <= docEl.clientWidth && body.scrollWidth <= body.clientWidth;
        });
        if (!checkFac) failures++;
        await ctxFac.close();
      }
    }

    if (failures > 0) {
      console.error(`Layout test failed: ${failures} viewport configurations had horizontal overflow.`);
      process.exit(1);
    } else {
      console.log(`Layout test passed: All 28 viewport configurations have zero horizontal overflow.`);
      process.exit(0);
    }
  } finally {
    await browser.close();
  }
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
