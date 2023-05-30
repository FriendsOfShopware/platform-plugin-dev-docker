<?php declare(strict_types=1);

use Shopware\Core\TestBootstrapper;

$projectDir = $_SERVER['SHOPWARE_BUILD_DIR'];
if (is_readable($projectDir . '/vendor/shopware/core/TestBootstrapper.php')) {
    require $projectDir . '/vendor/shopware/core/TestBootstrapper.php';
if (is_readable($projectDir . '/src/Core/TestBootstrapper.php')) {
    require $projectDir . '/src/Core/TestBootstrapper.php';
} elseif (is_readable(__DIR__ . '/TestBootstrapperFallback.php')) {
    // For old Shopware versions which do not have the TestBootstrapper we manually need
    // to set the kernel class
    $_SERVER['KERNEL_CLASS'] ??= 'Shopware\Production\Kernel';

    require __DIR__ . '/TestBootstrapperFallback.php';
}

return (new TestBootstrapper())
    ->setProjectDir($projectDir)
    ->setDatabaseUrl('mysql://root:root@localhost:3306/shopware')
;
