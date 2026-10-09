<?php
// Written on deploy from GitHub Actions secret BREVO_API_KEY.
return [
  'api_key' => getenv('BREVO_API_KEY') ?: '',
];
