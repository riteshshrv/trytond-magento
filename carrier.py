# -*- coding: utf-8 -*-
from trytond.pool import PoolMeta
from trytond import backend
from trytond.transaction import Transaction


__metaclass__ = PoolMeta
__all__ = [
    'SaleChannelCarrier',
]


class SaleChannelCarrier:
    __name__ = 'sale.channel.carrier'

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor

        # Use magento_instance_carrier table to hold this model
        if TableHandler.table_exist(cursor, 'magento_instance_carrier'):
            TableHandler.table_rename(
                cursor, 'magento_instance_carrier', cls._table
            )

            table = TableHandler(cursor, cls, module_name)
            table.column_rename('title', 'name')

        super(SaleChannelCarrier, cls).__register__(module_name)

    def get_magento_mapping(self):
        """
        Return code and title for magento

        Downstream modules can override this behaviour

        Return: (`code`, `title`)
        """
        return self.code, self.title
