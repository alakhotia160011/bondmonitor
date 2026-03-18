export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return res.status(500).json({ error: 'GITHUB_TOKEN not configured' });
  }

  try {
    const response = await fetch(
      'https://api.github.com/repos/alakhotia160011/bondmonitor/actions/workflows/refresh.yml/dispatches',
      {
        method: 'POST',
        headers: {
          'Authorization': `token ${token}`,
          'Accept': 'application/vnd.github.v3+json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ref: 'main' }),
      }
    );

    if (response.status === 204) {
      return res.status(200).json({ ok: true, message: 'Workflow triggered' });
    }

    const body = await response.text();
    return res.status(response.status).json({ error: body });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
}
