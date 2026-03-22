import { FormEvent, useEffect, useState } from "react";

import { testApi, type TestApiGetResponse, type TestApiPostResponse } from "../../services/api";

export function BackendApiDemo() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [getData, setGetData] = useState<TestApiGetResponse | null>(null);

  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<TestApiPostResponse | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await testApi.getTestData();
      setGetData(data);
    } catch {
      setError("Could not load data from backend. Make sure Django server is running on port 8000.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitError(null);
    setSubmitSuccess(null);

    if (!name.trim()) {
      setSubmitError("Name is required.");
      return;
    }

    if (!message.trim()) {
      setSubmitError("Message is required.");
      return;
    }

    setSubmitting(true);

    try {
      const data = await testApi.postTestData({
        name: name.trim(),
        message: message.trim(),
      });
      setSubmitSuccess(data);
      setName("");
      setMessage("");
    } catch {
      setSubmitError("Submission failed. Please check backend logs and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="max-w-7xl mx-auto px-6 pb-20">
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-border">
          <h3 className="text-2xl font-semibold text-foreground mb-3">GET /api/test/</h3>
          <p className="text-muted-foreground mb-4">
            This data is fetched from Django REST Framework when the component loads.
          </p>

          {loading ? <p className="text-primary">Loading backend data...</p> : null}
          {error ? <p className="text-red-600">{error}</p> : null}

          {getData ? (
            <div className="space-y-2 bg-accent/50 rounded-lg p-4 border border-border">
              <p>
                <span className="font-medium">Status:</span> {getData.status}
              </p>
              <p>
                <span className="font-medium">Message:</span> {getData.message}
              </p>
              <p>
                <span className="font-medium">Course:</span> {getData.data.course}
              </p>
              <p>
                <span className="font-medium">Backend:</span> {getData.data.backend}
              </p>
            </div>
          ) : null}

          <button
            onClick={loadData}
            className="mt-4 px-4 py-2 rounded-lg bg-primary text-white hover:opacity-90"
            type="button"
          >
            Refresh Data
          </button>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-border">
          <h3 className="text-2xl font-semibold text-foreground mb-3">POST /api/test/</h3>
          <p className="text-muted-foreground mb-4">
            Submit this form to send data from React to Django.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1" htmlFor="name">
                Name
              </label>
              <input
                id="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="w-full border border-border rounded-lg px-3 py-2"
                placeholder="Enter your name"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1" htmlFor="message">
                Message
              </label>
              <textarea
                id="message"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                className="w-full border border-border rounded-lg px-3 py-2 min-h-24"
                placeholder="Write a message"
              />
            </div>

            {submitError ? <p className="text-red-600 text-sm">{submitError}</p> : null}
            {submitSuccess ? (
              <div className="text-green-700 text-sm bg-green-50 border border-green-200 rounded-lg p-3">
                <p className="font-medium">Success</p>
                <p>{submitSuccess.message}</p>
              </div>
            ) : null}

            <button
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90"
              type="submit"
              disabled={submitting}
            >
              {submitting ? "Submitting..." : "Send to Backend"}
            </button>
          </form>
        </div>
      </div>
    </section>
  );
}
