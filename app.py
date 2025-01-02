import os
from datetime import datetime
import json
import pdfkit
import platform
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from products import PRODUCT_CATALOG

load_dotenv()

# Configure storage path for Render
STORAGE_PATH = '/opt/render/project/src/orders'
app = Flask(__name__)

# Configure pdfkit for both local and Render environments
if platform.system() == 'Windows':
    WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
else:
    # Path for Render/Linux
    WKHTMLTOPDF_PATH = '/usr/bin/wkhtmltopdf'

try:
    pdfkit_config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
except Exception as e:
    print(f"Error configuring pdfkit: {str(e)}")
    pdfkit_config = None

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
        
        os.makedirs(os.path.join(STORAGE_PATH, 'pdfs'), exist_ok=True)
        os.makedirs(os.path.join(STORAGE_PATH, 'orders'), exist_ok=True)
        
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
    order_id = data['customer']['poNumber'] or datetime.now().strftime('%Y%m%d_%H%M%S')
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
                <h1>Purchase Order #{data['customer']['poNumber']}</h1>
                <p>Date: {datetime.now().strftime('%Y-%m-%d')}</p>
            </div>
            
            <div class="order-info">
                <h3>Customer Information</h3>
                <p>Name: {data['customer']['name']}</p>
                <p>Email: {data['customer']['email']}</p>
                <p>Phone: {data['customer']['phone']}</p>
                <p>Address: {data['customer']['address']}</p>
            </div>

            <h3>Order Details</h3>
            <table>
                <tr>
                    <th>SKU</th>
                    <th>Item</th>
                    <th>Description</th>
                    <th>Quantity</th>
                    <th>Unit Cost</th>
                    <th>Total Cost</th>
                </tr>
        """
        
        order_total = 0
        
        for item in data['items']:
            base_price = item['basePrice']
            markup_percent = item['markup']
            quantity = item['quantity']
            description = item.get('description', 'No description available')  # Ensure you have 'description' in each item
            
            # Calculate the customer's price (base + markup)
            unit_price = base_price * (1 + markup_percent / 100)
            line_total = unit_price * quantity
            order_total += line_total
            
            html_content += f"""
                <tr>
                    <td>{item.get('sku', 'N/A')}</td>
                    <td>{item['name']}</td>
                    <td>{description}</td>
                    <td>{quantity}</td>
                    <td>${unit_price:.2f}</td>
                    <td>${line_total:.2f}</td>
                </tr>
            """
        
        # Include shipping costs if present
        if 'shipping' in data:
            shipping_cost = data['shipping']['cost']
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
