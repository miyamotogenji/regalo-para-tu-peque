const BREVO_API_KEY = process.env.BREVO_API_KEY || process.env.BREVO_KEY;

async function brevo(path, method, payload) {
  const res = await fetch('https://api.brevo.com/v3' + path, {
    method,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'api-key': BREVO_API_KEY,
    },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  const text = await res.text();
  let json = {};
  try { json = text ? JSON.parse(text) : {}; } catch (e) { json = { raw: text }; }
  return { status: res.status, json, text };
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'method' });
  if (!BREVO_API_KEY) return res.status(500).json({ error: 'missing_api_key' });

  let data = req.body;
  if (typeof data === 'string') {
    try { data = JSON.parse(data); } catch (e) { return res.status(400).json({ error: 'invalid' }); }
  }
  if (!data || !data.email) return res.status(400).json({ error: 'invalid' });

  const attributes = data.attributes || {};
  const listIds = data.listIds || [5, 6];

  const contact = await brevo('/contacts', 'POST', {
    email: data.email,
    attributes,
    listIds,
    updateEnabled: true,
  });

  // 201 created, 204 updated — both OK
  if (!(contact.status === 201 || contact.status === 204 || (contact.status >= 200 && contact.status < 300))) {
    return res.status(502).json({ error: 'brevo_contact', status: contact.status, body: contact.text });
  }

  // Send the PRUEBA Canva welcome (template 8) immediately — replaces bad default automation email
  const firstName =
    attributes.NOMBRE ||
    (attributes.NOMBRE_COMPLETO ? String(attributes.NOMBRE_COMPLETO).split(/\s+/)[0] : '') ||
    '';

  const mail = await brevo('/smtp/email', 'POST', {
    to: [{ email: data.email, name: attributes.NOMBRE_COMPLETO || firstName || data.email }],
    templateId: 8,
    params: {
      NOMBRE: firstName,
      contact: {
        NOMBRE: firstName,
        EMAIL: data.email,
        NOMBRE_COMPLETO: attributes.NOMBRE_COMPLETO || firstName,
      },
    },
  });

  if (!(mail.status >= 200 && mail.status < 300)) {
    // Contact was saved; still report partial success so download redirect works
    return res.status(200).json({
      ok: true,
      contact: true,
      emailWarning: true,
      emailStatus: mail.status,
      emailBody: mail.text,
    });
  }

  return res.status(200).json({ ok: true, contact: true, email: true });
};
