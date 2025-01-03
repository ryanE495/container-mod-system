import os
from datetime import datetime
import json
import pdfkit
import platform
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from products import PRODUCT_CATALOG

load_dotenv()

app = Flask(__name__)

# Configure storage path for both environments
if platform.system() == 'Windows':
    STORAGE_PATH = os.path.join(os.getcwd(), 'storage')
    WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
else:
    STORAGE_PATH = '/opt/render/project/src/storage'  # For Render deployment
    WKHTMLTOPDF_PATH = '/usr/bin/wkhtmltopdf'

# Create storage directories
os.makedirs(os.path.join(STORAGE_PATH, 'pdfs'), exist_ok=True)
os.makedirs(os.path.join(STORAGE_PATH, 'orders'), exist_ok=True)

# Configure pdfkit
try:
    pdfkit_config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
except Exception as e:
    print(f"Error configuring pdfkit: {str(e)}")
    pdfkit_config = None

def find_product_description(item_name, selected_option=None):
    """
    Search through the PRODUCT_CATALOG to find the description for a given item name.
    Returns the description or a default message if not found.
    """
    base_description = ""
    
    # For roll-up doors in "Ready to Ship"
    if "Roll Up Door" in item_name:
        base_description = "Includes weld in frame, threshold, brush seal, slide lock"
    
    # For windows
    elif "No Bars" in item_name or "With Bars" in item_name:
        base_description = "With weld-in frame"
    
    # Search through the catalog
    else:
        for category, items in PRODUCT_CATALOG.items():
            if category == 'windows':
                for window_type, options in items.items():
                    if item_name in options:
                        base_description = options[item_name].get('description', 'With weld-in frame')
                        break
            
            elif category == 'vents':
                if item_name in items:
                    base_description = items[item_name].get('description', '')
                    break
            
            elif category == 'ramps':
                if item_name in items:
                    desc = items[item_name].get('description', '')
                    capacity = items[item_name].get('capacity', '')
                    if desc and capacity:
                        base_description = f"{desc} - Capacity: {capacity}"
                    else:
                        base_description = desc or capacity
                    break
            
            elif category == 'weld_and_go_doors':
                if item_name in items:
                    base_description = items[item_name].get('description', '')
                    break
    
    # Special cases if no description found yet
    if not base_description:
        if "Shelf Brackets" in item_name:
            base_description = "Heavy-duty steel shelf mounting brackets"
        elif any(shelter_size in item_name for shelter_size in ["20'(L)", "40'(L)"]):
            base_description = "Container shelter with galvanized steel frame and heavy-duty tarp cover"
        elif "Container Caster Wheels" in item_name:
            base_description = "11,000 lbs capacity (set of 4)"
        else:
            base_description = "Standard configuration"

    # Add selected option to description if provided
    if selected_option:
        base_description = f"{base_description} - {selected_option}"

    return base_description

@app.route('/')
def index():
    return render_template('order_form.html', catalog=PRODUCT_CATALOG)

@app.route('/generate-quote', methods=['POST'])
def generate_quote():
    try:
        print("Starting quote generation...")
        
        if not request.is_json:
            print("Error: Request does not contain JSON data")
            return jsonify({
                'success': False,
                'error': 'Request must be JSON'
            }), 400
            
        data = request.json
        print(f"Received data: {data}")
        
        order_id = save_order(data)
        print(f"Order saved with ID: {order_id}")
        
        pdf_path = generate_pdf(order_id, data)
        print(f"PDF generated at: {pdf_path}")
        
        if os.path.exists(pdf_path):
            return jsonify({
                'success': True,
                'order_id': order_id,
                'message': 'PDF generated successfully'
            })
        else:
            print("Error: PDF file not created")
            return jsonify({
                'success': False,
                'error': 'PDF generation failed'
            }), 500
            
    except Exception as e:
        print(f"Error generating quote: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def save_order(data):
    order_id = data.get('customer', {}).get('poNumber') or datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = os.path.join(STORAGE_PATH, 'orders', f'order_{order_id}.json')
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=4)
    return order_id

def generate_pdf(order_id, data):
    try:
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .header {{ margin-bottom: 30px; }}
                .order-info {{ margin-bottom: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .total {{ font-weight: bold; margin-top: 20px; }}
                .summary {{ margin-top: 30px; padding: 15px; background-color: #f8f9fa; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Purchase Order #{data.get('customer', {}).get('poNumber', '')}</h1>
                <p>Date: {datetime.now().strftime('%Y-%m-%d')}</p>
            </div>
            
            <div class="order-info">
                <h3>Customer Information</h3>
                <p>Name: {data.get('customer', {}).get('name', '')}</p>
                <p>Email: {data.get('customer', {}).get('email', '')}</p>
                <p>Phone: {data.get('customer', {}).get('phone', '')}</p>
                <p>Address: {data.get('customer', {}).get('address', '')}</p>
            </div>

            <h3>Order Details</h3>
            <table>
                <tr>
                    <th>SKU</th>
                    <th>Item</th>
                    <th>Description</th>
                    <th>Quantity</th>
                    <th>Unit Price</th>
                    <th>Total</th>
                </tr>
        """
        
        order_total = 0
        
        for item in data.get('items', []):
            base_price = item.get('basePrice', 0)  # Use base price instead of marked-up price
            quantity = item.get('quantity', 0)
            selected_option = item.get('selectedOption', '')  # Get the selected option if available
            description = find_product_description(item.get('name', ''), selected_option)
            
            # Calculate total without markup
            line_total = base_price * quantity
            order_total += line_total
            
            html_content += f"""
                <tr>
                    <td>{item.get('sku', 'N/A')}</td>
                    <td>{item.get('name', '')}</td>
                    <td>{description}</td>
                    <td>{quantity}</td>
                    <td>${base_price:.2f}</td>
                    <td>${line_total:.2f}</td>
                </tr>
            """
        
        # Include shipping costs if present
        shipping_cost = data.get('shipping', {}).get('cost', 0)
        if shipping_cost:
            order_total += shipping_cost
            html_content += f"""
                <tr>
                    <td colspan="5">Shipping</td>
                    <td>${shipping_cost:.2f}</td>
                </tr>
            """

        html_content += f"""
            </table>
            
            <div class="summary">
                <p class="total">Total Amount: ${order_total:.2f}</p>
            </div>
            
            <div class="notes">
                <h3>Additional Notes</h3>
                <p>{data.get('notes', '')}</p>
            </div>
        </body>
        </html>
        """
        
        pdf_path = os.path.join(STORAGE_PATH, 'pdfs', f'order_{order_id}.pdf')
        pdfkit.from_string(
            html_content, 
            pdf_path,
            configuration=pdfkit_config,
            options={
                'encoding': 'UTF-8',
                'no-outline': None
            }
        )
        
        return pdf_path
        
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        raise

@app.route('/download-pdf/<order_id>')
def download_pdf(order_id):
    try:
        pdf_path = os.path.join(STORAGE_PATH, 'pdfs', f'order_{order_id}.pdf')
        if os.path.exists(pdf_path):
            return send_file(
                pdf_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'order_{order_id}.pdf'
            )
        else:
            return jsonify({
                'success': False,
                'error': 'PDF file not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)