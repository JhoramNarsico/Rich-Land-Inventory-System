# inventory/utils.py

from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa

def render_to_pdf(template_src, context_dict={}):
    """
    Renders a Django template into a PDF file and returns it as an HttpResponse.
    This version includes better error handling.
    """
    template = get_template(template_src)
    html  = template.render(context_dict)
    result = BytesIO()
    
    # The pisa.CreatePDF function is a more direct way to handle this.
    # It returns a pisa.pisaDocument object which has an 'err' attribute.
    pdf = pisa.CreatePDF(
            BytesIO(html.encode("UTF-8")), # The HTML content
            dest=result                        # The file-like object to write to
    )
    
    # Check if PDF creation was successful
    if not pdf.err:
        # If successful, return the PDF as a response.
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    
    # If there was an error, return a simple HTTP response with the error message.
    # This prevents the view from returning None and crashing the server.
    return HttpResponse(f'We had some errors converting to PDF: {pdf.err}', status=500)