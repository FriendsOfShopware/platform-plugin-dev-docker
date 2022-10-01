<?php declare(strict_types=1);

use Shopware\Core\TestBootstrapper;

$projectDir = $_SERVER['SHOPWARE_BUILD_DIR'];
if (is_readable($projectDir . '/vendor/shopware/core/TestBootstrapper.php')) {
    require $projectDir . '/vendor/shopware/core/TestBootstrapper.php';
} elseif (is_readable(__DIR__ . 'TestBootstrapperFallback.php')) {
    require __DIR__ . 'TestBootstrapperFallback.php';
}

return (new TestBootstrapper())
    ->setProjectDir($projectDir)
    ->setDatabaseUrl('mysql://root:root@localhost:3306/shopware')
;
