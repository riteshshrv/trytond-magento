# -*- coding: utf-8 -*-
import sys
import os
from decimal import Decimal

import unittest
from datetime import datetime
import pytz
from dateutil.relativedelta import relativedelta

import magento
from mock import patch, MagicMock
import trytond.tests.test_tryton
from trytond.transaction import Transaction
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT
from test_base import TestBase, load_json

DIR = os.path.abspath(os.path.normpath(
    os.path.join(
        __file__,
        '..', '..', '..', '..', '..', 'trytond'
    )
))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))


def mock_product_api(mock=None, data=None):
    if mock is None:
        mock = MagicMock(spec=magento.Product)

    handle = MagicMock(spec=magento.Product)
    handle.info.side_effect = \
        lambda sku, identifierType: load_json('products', sku)
    if data is None:
        handle.__enter__.return_value = handle
    else:
        handle.__enter__.return_value = data
    mock.return_value = handle
    return mock


def mock_order_api(mock=None, data=None):
    if mock is None:
        mock = MagicMock(spec=magento.Order)

    handle = MagicMock(spec=magento.Order)
    handle.info.side_effect = lambda id: load_json('orders', str(id))
    if data is None:
        handle.__enter__.return_value = handle
    else:
        handle.__enter__.return_value = data
    mock.return_value = handle
    return mock


def mock_customer_api(mock=None, data=None):
    if mock is None:
        mock = MagicMock(spec=magento.Customer)

    handle = MagicMock(spec=magento.Customer)
    handle.info.side_effect = lambda id: load_json('customers', str(id))
    if data is None:
        handle.__enter__.return_value = handle
    else:
        handle.__enter__.return_value = data
    mock.return_value = handle
    return mock


def mock_shipment_api(mock=None, data=None):
    if mock is None:
        mock = MagicMock(spec=magento.Shipment)

    handle = MagicMock(spec=magento.Shipment)
    handle.create.side_effect = lambda *args, **kwargs: 'Shipment created'
    handle.addtrack.side_effect = lambda *args, **kwargs: True
    if data is None:
        handle.__enter__.return_value = handle
    else:
        handle.__enter__.return_value = data
    mock.return_value = handle
    return mock


def mock_tier_price_api(mock=None, data=None):
    if mock is None:
        mock = MagicMock(spec=magento.ProductTierPrice)

    handle = MagicMock(spec=magento.ProductTierPrice)
    handle.update.side_effect = lambda *args, **kwargs: 'Prices Exported'
    if data is None:
        handle.__enter__.return_value = handle
    else:
        handle.__enter__.return_value = data
    mock.return_value = handle
    return mock


class TestSale(TestBase):
    """
    Tests import of sale order
    """

    def import_order_states(self, channel):
        """
        Import Order States
        """
        with Transaction().set_context({
            'current_channel': channel.id
        }):
            order_states_list = load_json('order-states', 'all')
            for code, name in order_states_list.iteritems():
                channel.create_order_state(code, name)

    def test_0005_import_sale_order_states(self):
        """
        Test the import and creation of sale order states for an channel
        """
        OrderState = POOL.get('sale.channel.order_state')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            states = []

            states_before_import = OrderState.search([])

            with Transaction().set_context({
                'current_channel': self.channel1.id
            }):

                order_states_list = load_json('order-states', 'all')
                for code, name in order_states_list.iteritems():
                    states.append(
                        self.channel1.create_order_state(code, name)
                    )

            states_after_import = OrderState.search([])

            self.assertTrue(states_after_import > states_before_import)

            for state in states:
                self.assertEqual(
                    state.channel.id, self.channel1.id
                )

    def test_0010_check_tryton_action(self):
        """
        Tests if correct tryton action is returned for each magento order state
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            self.assertEqual(
                self.channel1.get_default_tryton_action('new', 'new'),
                {
                    'action': 'process_manually',
                    'invoice_method': 'order',
                    'shipment_method': 'order'
                }
            )

            self.assertEqual(
                self.channel1.get_default_tryton_action('holded', 'holded'),
                {
                    'action': 'process_manually',
                    'invoice_method': 'order',
                    'shipment_method': 'order'
                }
            )

            self.assertEqual(
                self.channel1.get_default_tryton_action(
                    'pending_payment', 'pending_payment'),
                {
                    'action': 'import_as_past',
                    'invoice_method': 'order',
                    'shipment_method': 'invoice'
                }
            )

            self.assertEqual(
                self.channel1.get_default_tryton_action(
                    'payment_review', 'payment_review'),
                {
                    'action': 'import_as_past',
                    'invoice_method': 'order',
                    'shipment_method': 'invoice'
                }
            )

            self.assertEqual(
                self.channel1.get_default_tryton_action(
                    'closed', 'closed'),
                {
                    'action': 'import_as_past',
                    'invoice_method': 'order',
                    'shipment_method': 'order'
                }
            )

            self.assertEqual(
                self.channel1.get_default_tryton_action(
                    'complete', 'complete'),
                {
                    'action': 'import_as_past',
                    'invoice_method': 'order',
                    'shipment_method': 'order'
                }
            )

            self.assertEqual(
                self.channel1.get_default_tryton_action(
                    'processing', 'processing'),
                {
                    'action': 'process_automatically',
                    'invoice_method': 'order',
                    'shipment_method': 'order'
                }
            )

            self.assertEqual(
                self.channel1.get_default_tryton_action(
                    'cancelled', 'cancelled'),
                {
                    'action': 'do_not_import',
                    'invoice_method': 'manual',
                    'shipment_method': 'manual'
                }
            )

    def test_0020_import_carriers(self):
        """
        Test If all carriers are being imported from magento
        """
        SaleChannelCarrier = POOL.get('sale.channel.carrier')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            carriers_before_import = SaleChannelCarrier.search([])
            with Transaction().set_context({
                    'current_channel': self.channel1.id
            }):
                carriers = []
                carriers_data = load_json('carriers', 'shipping_methods')
                for data in carriers_data:
                    carriers.append({
                        'name': data['label'],
                        'code': data['code'],
                        'channel': self.channel1.id,
                    })
                SaleChannelCarrier.create(carriers)

                carriers_after_import = SaleChannelCarrier.search([])

                self.assertTrue(carriers_after_import > carriers_before_import)

    def test_0030_import_sale_order_with_products_with_new(self):
        """
        Tests import of sale order using magento data with magento state as new
        """
        Sale = POOL.get('sale.sale')
        Party = POOL.get('party.party')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            self.import_order_states(self.channel1)

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '100000001')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                            'magento.Product', mock_product_api(), create=True):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(order.channel_tax_amount, Decimal('5'))
                self.assertEqual(order.state, 'confirmed')
                self.assertFalse(order.has_channel_exception)

                orders = Sale.search([])
                self.assertEqual(len(orders), 1)

                # Item lines + shipping line should be equal to lines on tryton
                self.assertEqual(
                    len(order.lines), len(order_data['items']) + 1
                )

    def test_0032_import_sale_order_without_firstname_and_lastname(self):
        """
        Tests import of sale order using magento data without customer firstname
        and lastname
        """
        Sale = POOL.get('sale.sale')
        Party = POOL.get('party.party')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            self.import_order_states(self.channel1)

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '100000002')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                            'magento.Product', mock_product_api(), create=True):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(order.state, 'confirmed')
                self.assertFalse(order.has_channel_exception)

                orders = Sale.search([])
                self.assertEqual(len(orders), 1)

                # Item lines + shipping line should be equal to lines on tryton
                self.assertEqual(
                    len(order.lines), len(order_data['items']) + 1
                )

    def test_0033_import_sale_order_with_invalid_subdivision(self):
        """
        Tests import of sale order using magento data with invalid subdivision
        """
        Sale = POOL.get('sale.sale')
        Party = POOL.get('party.party')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            self.import_order_states(self.channel1)

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '100000001-invalid-state')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                            'magento.Product', mock_product_api(), create=True):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(order.state, 'confirmed')
                self.assertFalse(order.has_channel_exception)

                orders = Sale.search([])
                self.assertEqual(len(orders), 1)

                # Item lines + shipping line should be equal to lines on tryton
                self.assertEqual(
                    len(order.lines), len(order_data['items']) + 1
                )

    def test_0035_import_sale_order_with_products_with_processing(self):
        """
        Tests import of sale order using magento data with magento state as
        processing
        """
        Sale = POOL.get('sale.sale')
        Party = POOL.get('party.party')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            self.import_order_states(self.channel1)

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '100000001-processing')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                            'magento.Product', mock_product_api(), create=True
                    ):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(order.state, 'processing')

                orders = Sale.search([])
                self.assertEqual(len(orders), 1)

                # Item lines + shipping line should be equal to lines on tryton
                self.assertEqual(
                    len(order.lines), len(order_data['items']) + 1
                )

    def test_0040_find_or_create_order_using_increment_id(self):
        """
        Tests finding and creating order using increment id
        """
        Sale = POOL.get('sale.sale')
        Party = POOL.get('party.party')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            self.import_order_states(self.channel1)
            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '100000001')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento increment_id
                    with patch('magento.Order', mock_order_api(), create=True):
                        with patch(
                            'magento.Product', mock_product_api(),
                            create=True
                        ):
                            order = \
                                Sale.find_or_create_using_magento_increment_id(
                                    order_data['increment_id']
                                )
                self.assertEqual(order.state, 'confirmed')

                orders = Sale.search([])

                self.assertEqual(len(orders), 1)

                # Item lines + shipping line should be equal to lines on tryton
                self.assertEqual(
                    len(order.lines), len(order_data['items']) + 1
                )

    def test_0050_export_order_status_to_magento(self):
        """
        Tests if order status is exported to magento
        """
        Sale = POOL.get('sale.sale')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            self.import_order_states(self.channel1)

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '100000001')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    self.Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                            'magento.Product', mock_product_api(), create=True):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(order.state, 'confirmed')

                self.assertEqual(len(Sale.search([])), 1)

                with patch('magento.Order', mock_order_api(), create=True):
                    order_exported = \
                        self.channel1.export_order_status()

                    self.assertEqual(len(order_exported), 1)
                    self.assertEqual(order_exported[0], order)

    def test_0060_export_order_status_with_last_order_export_time_case1(self):
        """
        Tests that sale cannot be exported if last order export time is
        greater than sale's write date
        """
        Sale = POOL.get('sale.sale')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            self.import_order_states(self.channel1)

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '100000001')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    self.Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                            'magento.Product', mock_product_api(), create=True):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(order.state, 'confirmed')
                self.assertEqual(len(Sale.search([])), 1)

                export_date = datetime.utcnow() + relativedelta(days=1)
                self.channel1.last_order_export_time = export_date
                self.channel1.save()

                self.assertTrue(
                    self.channel1.last_order_export_time > order.write_date
                )

                with patch('magento.Order', mock_order_api(), create=True):
                    order_exported = self.channel1.export_order_status()

                    self.assertEqual(len(order_exported), 0)

    def test_0050_export_shipment(self):
        """
        Tests if shipments status is being exported for all the shipments
        related to store view
        """
        Sale = POOL.get('sale.sale')
        Party = POOL.get('party.party')
        Category = POOL.get('product.category')
        Carrier = POOL.get('carrier')
        ProductTemplate = POOL.get('product.template')
        SaleChannelCarrier = POOL.get('sale.channel.carrier')
        Shipment = POOL.get('stock.shipment.out')
        Uom = POOL.get('product.uom')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                order_states_list = load_json('order-states', 'all')
                for code, name in order_states_list.iteritems():
                    self.channel1.create_order_state(code, name)

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '100000001')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    party = Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                            'magento.Product', mock_product_api(), create=True
                    ):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                carriers = []
                carriers_data = load_json('carriers', 'shipping_methods')
                for data in carriers_data:
                    carriers.append({
                        'name': data['label'],
                        'code': data['code'],
                        'channel': self.channel1.id,
                    })
                mag_carriers = SaleChannelCarrier.create(carriers)

                uom, = Uom.search([('name', '=', 'Unit')], limit=1)
                product, = ProductTemplate.create([
                    {
                        'name': 'Shipping product',
                        'type': 'service',
                        'account_expense': self.get_account_by_kind('expense'),
                        'account_revenue': self.get_account_by_kind('revenue'),
                        'default_uom': uom.id,
                        'sale_uom': uom.id,
                        'products': [('create', [{
                            'code': 'code',
                            'description': 'This is a product description',
                            'list_price': Decimal('100'),
                            'cost_price': Decimal('1'),
                        }])]
                    }]
                )

                # Create carrier
                carrier, = Carrier.create([{
                    'party': party.id,
                    'carrier_product': product.products[0].id,
                }])
                SaleChannelCarrier.write([mag_carriers[0]], {
                    'carrier': carrier.id,
                })

                Sale.write([order], {'invoice_method': 'manual'})
                order = Sale(order.id)
                Sale.confirm([order])
                with Transaction().set_user(0, set_context=True):
                    Sale.process([order])
                shipment, = Shipment.search([])

                Shipment.assign([shipment])
                Shipment.pack([shipment])
                Shipment.done([shipment])

                shipment = Shipment(shipment.id)

                self.assertFalse(shipment.magento_increment_id)

                with patch(
                    'magento.Shipment', mock_shipment_api(), create=True
                ):

                    self.channel1.export_shipment_status_to_magento()

                    shipment = Shipment(shipment.id)
                    self.assertTrue(shipment.magento_increment_id)

    def test_0070_export_order_status_with_last_order_export_time_case2(self):
        """
        Tests that sale can be exported if last order export time is
        smaller than sale's write date
        """
        Sale = POOL.get('sale.sale')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            self.import_order_states(self.channel1)

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '100000001')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    self.Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                            'magento.Product', mock_product_api(), create=True):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(order.state, 'confirmed')
                self.assertEqual(len(Sale.search([])), 1)

                export_date = datetime.utcnow() - relativedelta(days=1)
                self.Channel.write([self.channel1], {
                    'last_order_export_time': export_date
                })

                self.assertTrue(
                    self.channel1.last_order_export_time < order.write_date
                )

                with patch('magento.Order', mock_order_api(), create=True):
                    order_exported = self.channel1.export_order_status()

                    self.assertEqual(len(order_exported), 1)
                    self.assertEqual(order_exported[0], order)

    def test_0080_import_sale_order_with_bundle_product(self):
        """
        Tests import of sale order with bundle product using magento data
        """
        Sale = POOL.get('sale.sale')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                order_states_list = load_json('order-states', 'all')
                for code, name in order_states_list.iteritems():
                    self.channel1.create_order_state(code, name)

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '300000001')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    self.Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                        'magento.Product', mock_product_api(), create=True
                    ):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(order.state, 'confirmed')

                orders = Sale.search([])
                self.assertEqual(len(orders), 1)

                # Item lines + shipping line should be equal to lines on tryton
                self.assertEqual(len(order.lines), 2)

                self.assertEqual(
                    order.total_amount, Decimal(order_data['base_grand_total'])
                )

                # There should be a BoM for the bundle product
                product = self.channel1.import_product('VGN-TXN27N-BW')

                self.assertEqual(len(product.boms), 1)

                # virtual product is ignored
                self.assertEqual(
                    len(product.boms[0].bom.inputs), 1
                )

    def test_0090_import_sale_order_with_bundle_product_check_duplicate(self):
        """
        Tests import of sale order with bundle product using magento data
        This tests that the duplication of BoMs doesnot happen
        """
        Sale = POOL.get('sale.sale')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                order_states_list = load_json('order-states', 'all')
                for code, name in order_states_list.iteritems():
                    self.channel1.create_order_state(code, name)

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                order_data = load_json('orders', '300000001')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    self.Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context({'company': self.company.id}):
                    # Create sale order using magento data
                    with patch(
                        'magento.Product', mock_product_api(), create=True
                    ):
                        Sale.find_or_create_using_magento_data(order_data)

                # There should be a BoM for the bundle product
                product = self.channel1.import_product(
                    'VGN-TXN27N-BW'
                )
                self.assertTrue(len(product.boms), 1)
                self.assertTrue(len(product.boms[0].bom.inputs), 2)

                order_data = load_json('orders', '300000001-a')

                # Create sale order using magento data
                with patch('magento.Product', mock_product_api(), create=True):
                    Sale.find_or_create_using_magento_data(order_data)

                # There should be a BoM for the bundle product
                product = self.channel1.import_product(
                    'VGN-TXN27N-BW'
                )
                self.assertEqual(len(product.boms), 1)

                # virtual product is ignored
                self.assertEqual(len(product.boms[0].bom.inputs), 1)

    def test_0100_import_sale_with_bundle_plus_child_separate(self):
        """
        Tests import of sale order with bundle product using magento data
        One of the children of the bundle is bought separately too
        Make sure that the lines are created correctly
        """
        Sale = POOL.get('sale.sale')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                order_states_list = load_json('order-states', 'all')
                for code, name in order_states_list.iteritems():
                    self.channel1.create_order_state(code, name)

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                order_data = load_json('orders', '100000004')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    self.Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context({'company': self.company.id}):
                    # Create sale order using magento data
                    with patch(
                        'magento.Product', mock_product_api(), create=True
                    ):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(
                    order.total_amount, Decimal(order_data['base_grand_total'])
                )

                # Item lines + shipping line should be equal to lines on tryton
                self.assertEqual(len(order.lines), 3)

    def test_0105_import_order_in_draft_state(self):
        """
        Tests that orders can not be imported in draft state
        """
        Sale = POOL.get('sale.sale')
        Party = POOL.get('party.party')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                order_states_list = load_json('order-states', 'all')
                for code, name in order_states_list.iteritems():
                    self.channel1.create_order_state(code, name)

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '100000001-draft')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                            'magento.Product', mock_product_api(), create=True
                    ):
                        Sale.find_or_create_using_magento_data(
                            order_data
                        )

                # Order has not been imported
                self.assertFalse(Sale.search([]))

    def test_0110_export_product_tier_prices_to_magento(self):
        """
        Tests if tier prices from product listing is exported to magento
        """
        Sale = POOL.get('sale.sale')
        Category = POOL.get('product.category')
        ChannelListing = POOL.get('product.product.channel_listing')
        ProductPriceTier = POOL.get('product.price_tier')
        Product = POOL.get('product.product')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            self.import_order_states(self.channel1)

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                self.assertEqual(ChannelListing.search([], count=True), 0)
                self.assertEqual(Product.search([], count=True), 0)

                order_data = load_json('orders', '100000001')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    self.Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                            'magento.Product', mock_product_api(), create=True):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(Product.search([], count=True), 2)

                product1, product2 = Product.search([])
                self.assertEqual(ChannelListing.search([], count=True), 2)

                product_listing1, = ChannelListing.search([
                    ('product', '=', product1.id)
                ])
                product_listing2, = ChannelListing.search([
                    ('product', '=', product2.id)
                ])

                self.assertFalse(product_listing1.price_tiers)
                self.assertFalse(product_listing2.price_tiers)

                # Create price tiers for listing
                ProductPriceTier.create([{
                    'product_listing': product_listing1.id,
                    'quantity': 10,
                }])
                ProductPriceTier.create([{
                    'product_listing': product_listing2.id,
                    'quantity': 10,
                }])

                self.assertEqual(order.state, 'confirmed')

                self.assertEqual(len(Sale.search([])), 1)

                # Export tier prices to magento
                with patch(
                    'magento.ProductTierPrice', mock_tier_price_api(),
                    create=True
                ):
                    product_listings = \
                        self.channel1.export_product_prices()

                    self.assertEqual(product_listings, 2)
                self.assertEqual(
                    self.channel1.last_product_price_export_time.date(),
                    datetime.utcnow().date()
                )

    def test_0120_export_channel_tier_prices_to_magento(self):
        """
        Tests if tier prices from product listing is exported to magento
        """
        Sale = POOL.get('sale.sale')
        Category = POOL.get('product.category')
        MagentoPriceTier = POOL.get('sale.channel.magento.price_tier')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            self.import_order_states(self.channel1)

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '100000001')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    self.Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                            'magento.Product', mock_product_api(), create=True):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertFalse(self.channel1.magento_price_tiers)

                # Add price tiers to channel
                MagentoPriceTier.create([{
                    'channel': self.channel1.id,
                    'quantity': 10,
                }])

                self.assertEqual(order.state, 'confirmed')

                self.assertEqual(len(Sale.search([])), 1)

                # Export tier prices to magento
                with patch(
                    'magento.ProductTierPrice', mock_tier_price_api(),
                    create=True
                ):
                    product_listings = \
                        self.channel1.export_product_prices()

                    self.assertEqual(product_listings, 2)
                self.assertEqual(
                    self.channel1.last_product_price_export_time.date(),
                    datetime.utcnow().date()
                )

    def test_0110_export_tier_prices_to_magento_using_last_import_time(self):
        """
        Tests if tier prices is exported for the product only which has changed
        after last tier price export time
        """
        Sale = POOL.get('sale.sale')
        Category = POOL.get('product.category')
        ChannelListing = POOL.get('product.product.channel_listing')
        ProductPriceTier = POOL.get('product.price_tier')
        Product = POOL.get('product.product')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            self.import_order_states(self.channel1)

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                self.assertEqual(ChannelListing.search([], count=True), 0)
                self.assertEqual(Product.search([], count=True), 0)

                order_data = load_json('orders', '100000001')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    self.Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                            'magento.Product', mock_product_api(), create=True):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(order.state, 'confirmed')

                self.assertEqual(len(Sale.search([])), 1)

                self.assertEqual(Product.search([], count=True), 2)

                product1, product2 = Product.search([])
                self.assertEqual(ChannelListing.search([], count=True), 2)

                product_listing1, = ChannelListing.search([
                    ('product', '=', product1.id)
                ])
                product_listing2, = ChannelListing.search([
                    ('product', '=', product2.id)
                ])

                self.assertFalse(product_listing1.price_tiers)
                self.assertFalse(product_listing2.price_tiers)

                # Create price tiers for listing
                ProductPriceTier.create([{
                    'product_listing': product_listing1.id,
                    'quantity': 10,
                }])
                ProductPriceTier.create([{
                    'product_listing': product_listing2.id,
                    'quantity': 10,
                }])

                self.channel1.last_product_price_export_time = \
                    datetime.utcnow()
                self.channel1.save()

                # Change product1's values and prices will get exported
                # only for this updated product only
                product1.template.cost_price = 20
                product1.template.save()

                self.assertTrue(
                    product1.template.write_date >
                    self.channel1.last_product_price_export_time
                )

                # Export tier prices to magento
                with patch(
                    'magento.ProductTierPrice', mock_tier_price_api(),
                    create=True
                ):
                    product_listings = \
                        self.channel1.export_product_prices()

                    self.assertEqual(product_listings, 1)

    def test_0090_find_or_create_order_using_magento_id(self):
        """
        Tests if magento_id is not copied in duplicate sales
        """
        Sale = POOL.get('sale.sale')
        Party = POOL.get('party.party')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            self.import_order_states(self.channel1)
            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '100000001')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento increment_id
                    with patch('magento.Order', mock_order_api(), create=True):
                        with patch(
                            'magento.Product', mock_product_api(),
                            create=True
                        ):
                            order = \
                                Sale.find_or_create_using_magento_increment_id(
                                    order_data['increment_id']
                                )
                self.assertEqual(order.state, 'confirmed')

                orders = Sale.search([])
                self.assertIsNotNone(order.magento_id)

                self.assertEqual(len(orders), 1)

                # Item lines + shipping line should be equal to lines on tryton
                self.assertEqual(
                    len(order.lines), len(order_data['items']) + 1
                )

                new_sales = Sale.copy(orders)
                self.assertTrue(new_sales)
                self.assertEqual(len(new_sales), 1)
                self.assertIsNone(new_sales[0].magento_id)

    def test_0130_import_sale_order_with_payment_info(self):
        """
        Tests import of sale order with payment info
        """
        Sale = POOL.get('sale.sale')
        Category = POOL.get('product.category')
        PaymentGateway = POOL.get('payment_gateway.gateway')
        MagentoPaymentGateway = POOL.get('magento.instance.payment_gateway')

        def create_gateways():
            cash_gateway, = PaymentGateway.create([{
                'name': 'Manual Gateway',
                'journal': self.cash_journal.id,
                'provider': 'self',
                'method': 'manual',
            }])

            magento_gateway, = MagentoPaymentGateway.create([{
                'name': 'checkmo',
                'title': 'checkmo',
                'gateway': cash_gateway.id,
                'channel': self.channel1.id,
            }])

        # CASE 1: When payment is not complete on magento, we dont import
        # them in tryton
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            create_gateways()

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                order_states_list = load_json('order-states', 'all')
                for code, name in order_states_list.iteritems():
                    self.channel1.create_order_state(code, name)

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '300000001')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    self.Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                        'magento.Product', mock_product_api(), create=True
                    ):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(order.state, 'confirmed')

                orders = Sale.search([])
                self.assertEqual(len(orders), 1)
                self.assertEqual(len(order.lines), 2)

                self.assertEqual(len(order.payments), 0)

        # CASE 2: When payment is completed on magento, we import
        # payment in  tryton and complete it here.
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            create_gateways()

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                order_states_list = load_json('order-states', 'all')
                for code, name in order_states_list.iteritems():
                    self.channel1.create_order_state(code, name)

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json('orders', '300000001-completed-payment')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    self.Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                        'magento.Product', mock_product_api(), create=True
                    ):
                        order = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(order.state, 'confirmed')

                orders = Sale.search([])
                self.assertEqual(len(orders), 1)
                self.assertEqual(len(order.lines), 2)

                payment, = order.payments
                self.assertEqual(payment.amount, order.total_amount)
                self.assertEqual(payment.amount_available, Decimal('0'))
                self.assertEqual(len(payment.payment_transactions), 1)

    def test_140_check_date_conversion_est_to_utc(self):
        """
        Tests conversion of date in case user selects a timezone
        field.
        """
        Sale = POOL.get('sale.sale')
        Category = POOL.get('product.category')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            self.import_order_states(self.channel1)

            with Transaction().set_context({
                'current_channel': self.channel1.id,
            }):

                category_tree = load_json('categories', 'category_tree')
                Category.create_tree_using_magento_data(category_tree)

                order_data = load_json('orders', '100000002')

                with patch(
                        'magento.Customer', mock_customer_api(), create=True):
                    self.Party.find_or_create_using_magento_id(
                        order_data['customer_id']
                    )

                with Transaction().set_context(company=self.company):
                    # Create sale order using magento data
                    with patch(
                            'magento.Product', mock_product_api(), create=True):
                        m_sale = Sale.find_or_create_using_magento_data(
                            order_data
                        )

                self.assertEqual(
                    self.channel1.timezone, 'US/Eastern')

                timezone = pytz.timezone(self.channel1.timezone)
                sale_time = datetime.strptime(
                    order_data['created_at'], '%Y-%m-%d %H:%M:%S'
                )
                sale_time = timezone.localize(sale_time)
                utc_sale_time = sale_time.astimezone(pytz.utc).date()

                self.assertEqual(
                    m_sale.sale_date, utc_sale_time
                )


def suite():
    """
    Test Suite
    """
    test_suite = trytond.tests.test_tryton.suite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestSale)
    )
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
