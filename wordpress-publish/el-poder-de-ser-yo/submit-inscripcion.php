<?php
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
  http_response_code(204);
  exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
  http_response_code(405);
  echo json_encode(['error' => 'method']);
  exit;
}

$raw = file_get_contents('php://input');
$data = json_decode($raw, true);
if (!$data || empty($data['email'])) {
  http_response_code(400);
  echo json_encode(['error' => 'invalid']);
  exit;
}

$apiKey = getenv('BREVO_API_KEY');
if (!$apiKey) {
  $cfgFile = __DIR__ . '/brevo-config.php';
  if (is_file($cfgFile)) {
    $cfg = include $cfgFile;
    $apiKey = is_array($cfg) ? ($cfg['api_key'] ?? '') : '';
  }
}

if (!$apiKey) {
  http_response_code(500);
  echo json_encode(['error' => 'missing_api_key']);
  exit;
}

function brevo_post($apiKey, $path, $payload) {
  $json = json_encode($payload, JSON_UNESCAPED_UNICODE);
  $ch = curl_init('https://api.brevo.com/v3' . $path);
  $opts = [
    CURLOPT_POST => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER => [
      'Accept: application/json',
      'Content-Type: application/json',
      'api-key: ' . $apiKey,
    ],
    CURLOPT_POSTFIELDS => $json,
    CURLOPT_TIMEOUT => 45,
  ];
  if (stripos(PHP_OS_FAMILY, 'Windows') === 0) {
    $opts[CURLOPT_SSL_VERIFYPEER] = false;
    $opts[CURLOPT_SSL_VERIFYHOST] = 0;
  }
  curl_setopt_array($ch, $opts);
  $resp = curl_exec($ch);
  $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
  $cerr = curl_error($ch);
  curl_close($ch);
  return [$code, $resp, $cerr];
}

$contactPayload = [
  'email' => $data['email'],
  'attributes' => $data['attributes'] ?? new stdClass(),
  'listIds' => $data['listIds'] ?? [9],
  'updateEnabled' => true,
];

[$code, $resp, $cerr] = brevo_post($apiKey, '/contacts', $contactPayload);
if ($resp === false) {
  http_response_code(502);
  echo json_encode(['error' => 'curl', 'detail' => $cerr]);
  exit;
}

$contactOk = ($code === 201 || $code === 204 || ($code >= 200 && $code < 300));
if (!$contactOk) {
  http_response_code(502);
  echo json_encode(['error' => 'brevo', 'status' => $code, 'body' => $resp]);
  exit;
}

$attrs = is_array($data['attributes'] ?? null) ? $data['attributes'] : [];
$html = '<p><strong>Nueva inscripción — El Poder de Ser Yo</strong></p><ul>'
  . '<li>Nombre: ' . htmlspecialchars($attrs['NOMBRE_COMPLETO'] ?? '') . '</li>'
  . '<li>Email: ' . htmlspecialchars($data['email']) . '</li>'
  . '<li>WhatsApp: ' . htmlspecialchars($attrs['TELEFONO_WHATSAPP'] ?? '') . '</li>'
  . '<li>País: ' . htmlspecialchars($attrs['PAIS'] ?? '') . '</li>'
  . '<li>Rol: ' . htmlspecialchars($attrs['ROL'] ?? '') . '</li>'
  . '<li>Hijos: ' . htmlspecialchars(($attrs['CANTIDAD_HIJOS'] ?? '') . ' — ' . ($attrs['EDAD_HIJOS'] ?? '')) . '</li>'
  . '<li>Interés: ' . htmlspecialchars($attrs['INTERES_TALLER'] ?? '') . '</li>'
  . '<li>Fuente: ' . htmlspecialchars($attrs['COMO_ENTERASTE'] ?? '') . '</li>'
  . '<li>Recibir info: ' . htmlspecialchars($attrs['RECIBIR_INFO'] ?? '') . '</li>'
  . '<li>Pregunta: ' . htmlspecialchars($attrs['PREGUNTA_ABIERTA'] ?? '') . '</li>'
  . '</ul>';

$mail = [
  'sender' => ['name' => 'Todos a Bordo CR', 'email' => 'todosabordocr@gmail.com'],
  'to' => [['email' => 'todosabordocr@gmail.com']],
  'subject' => 'Inscripción taller + comprobante — El Poder de Ser Yo',
  'htmlContent' => $html,
];

if (!empty($data['comprobante']['content'])) {
  $name = preg_replace('/[^\w.\-]+/', '_', $data['comprobante']['name'] ?? 'comprobante.pdf');
  $mail['attachment'] = [[
    'content' => $data['comprobante']['content'],
    'name' => substr($name ?: 'comprobante.pdf', 0, 80),
  ]];
  $html .= '<p>Comprobante de pago adjunto.</p>';
  $mail['htmlContent'] = $html;
} else {
  $mail['htmlContent'] = $html . '<p>Sin comprobante adjunto.</p>';
}

brevo_post($apiKey, '/smtp/email', $mail);

http_response_code(200);
echo json_encode(['ok' => true]);
