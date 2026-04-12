<?php
class BackendCombinedConfig {
    public static function GetBackendCombinedConfig() {
        return array(
            'backends' => array(
                'i' => array(
                    'name' => 'BackendIMAP',
                ),
                'c' => array(
                    'name' => 'BackendCalDAV',
                ),
                'd' => array(
                    'name' => 'BackendCardDAV',
                ),
            ),
            'delimiter' => '/',
            'folderbackend' => array(
                SYNC_FOLDER_TYPE_INBOX => 'i',
                SYNC_FOLDER_TYPE_DRAFTS => 'i',
                SYNC_FOLDER_TYPE_WASTEBASKET => 'i',
                SYNC_FOLDER_TYPE_SENTMAIL => 'i',
                SYNC_FOLDER_TYPE_OUTBOX => 'i',
                SYNC_FOLDER_TYPE_TASK => 'c',
                SYNC_FOLDER_TYPE_APPOINTMENT => 'c',
                SYNC_FOLDER_TYPE_CONTACT => 'd',
                SYNC_FOLDER_TYPE_NOTE => 'i',
            ),
            'rootcreatefolderbackend' => 'i',
        );
    }
}
