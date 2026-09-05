<?php

declare(strict_types=1);

/**
 * Phase 1 离线验收桩：只复刻 Luna V3 HTTP 协议，不执行 AI 推理。
 * 容器不映射宿主机端口，只允许业务容器通过 Compose 内网访问。
 */

header('Content-Type: application/json; charset=utf-8');

function respond(array $payload, int $status = 200): void
{
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function requestJson(): array
{
    $raw = file_get_contents('php://input');
    $decoded = json_decode($raw ?: '[]', true);
    return is_array($decoded) ? $decoded : [];
}

function hasFixtureToken(): bool
{
    $headers = function_exists('getallheaders') ? getallheaders() : [];
    $token = $headers['JWTHEADER'] ?? $headers['Jwtheader'] ?? $headers['jwtheader'] ?? '';
    return hash_equals((string)getenv('PHASE1_LUNA_STUB_TOKEN'), (string)$token);
}

$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);

if ($path === '/healthz') {
    respond(['ok' => true, 'mode' => 'phase1-offline-fixture']);
}

if ($path === '/api/app/authentication' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $body = requestJson();
    $valid = hash_equals((string)getenv('PHASE1_LUNA_STUB_SECRET'), (string)($body['secret'] ?? ''))
        && hash_equals((string)getenv('PHASE1_LUNA_STUB_SECRET_KEY'), (string)($body['secretKey'] ?? ''));
    if (!$valid) {
        respond(['code' => 4001, 'message' => 'fixture credentials rejected', 'data' => null]);
    }
    respond([
        'code' => 1,
        'message' => 'success',
        'data' => ['accessToken' => (string)getenv('PHASE1_LUNA_STUB_TOKEN')],
    ]);
}

if (!hasFixtureToken()) {
    respond(['code' => 4002, 'message' => 'fixture token rejected', 'data' => null]);
}

if ($path === '/api/userMessage/checkUserImageUpload' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    // Guzzle 的流式 multipart 在不同 PHP SAPI 下可能不进入 $_FILES；验收桩同时
    // 要求 multipart Content-Type 和非空 Content-Length，避免把空请求判为上传成功。
    $contentType = strtolower((string)($_SERVER['CONTENT_TYPE'] ?? ''));
    $contentLength = (int)($_SERVER['CONTENT_LENGTH'] ?? 0);
    $hasParsedFile = !empty($_FILES['file']['tmp_name']) && is_uploaded_file($_FILES['file']['tmp_name']);
    $hasStreamedMultipart = str_contains($contentType, 'multipart/form-data') && $contentLength > 0;
    if (!$hasParsedFile && !$hasStreamedMultipart) {
        respond(['code' => 9001, 'message' => 'fixture upload missing', 'data' => null]);
    }
    respond([
        'code' => 1,
        'message' => 'success',
        'data' => [
            'id' => 910001,
            'filePath' => 'synthetic-input.png',
            'fileFaceList' => [[
                'id' => 910101,
                'boundingBoxLeft' => 0.24,
                'boundingBoxTop' => 0.12,
                'boundingBoxWidth' => 0.52,
                'boundingBoxHeight' => 0.52,
                'is_default' => 1,
            ]],
        ],
    ]);
}

if ($path === '/api/userMessage/createSwapEnhanceV3' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $body = requestJson();
    if (!$body || !isset($body[0]['up_file_id'], $body[0]['targetFileId'], $body[0]['mapping'])) {
        respond(['code' => 4220, 'message' => 'invalid FaceMappingList fixture payload', 'data' => null]);
    }
    // The cloned schema stores upstream task IDs in varchar(10). Keep the
    // fixture unique at millisecond granularity without widening production DB.
    $messageId = (int)(((int)round(microtime(true) * 1000)) % 10000000000);
    respond([
        'code' => 1,
        'message' => 'success',
        'data' => [
            'messageId' => $messageId,
            'consumingTime' => 1,
        ],
    ]);
}

if ($path === '/api/userMessage/polling' && $_SERVER['REQUEST_METHOD'] === 'GET') {
    $messageId = (int)($_GET['messageId'] ?? 0);
    respond([
        'code' => 1,
        'message' => 'success',
        'data' => [
            'id' => $messageId,
            'status' => 1,
            'errorMsg' => null,
            'messageList' => [[
                'id' => 9102001,
                'status' => 1,
                'sourceFilePath' => 'synthetic-result.png',
                'tagName' => 'Phase 1 离线验收',
                'receiveTime' => time(),
            ]],
            'consumingTime' => 1,
        ],
    ]);
}

if ($path === '/api/userMessage/getMaterialFileFaceList' && $_SERVER['REQUEST_METHOD'] === 'GET') {
    respond([
        'code' => 1,
        'message' => 'success',
        'data' => [[
            'id' => 910201,
            'boundingBoxLeft' => 0.25,
            'boundingBoxTop' => 0.15,
            'boundingBoxWidth' => 0.5,
            'boundingBoxHeight' => 0.5,
            'is_default' => 1,
        ]],
    ]);
}

respond(['code' => 4040, 'message' => 'fixture route not found', 'data' => null], 404);
